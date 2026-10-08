"""Real HTTP hops, SQL and Redis instrumentation in an isolated SDK process."""
import io
import json
import logging
import os
import socket
import threading
import time
from unittest.mock import patch

import httpx
import redis
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, BatchSpanProcessor

from seckill_observability.http import RequestContextMiddleware
from seckill_observability.logging import ContextFilter, JsonFormatter
from seckill_observability.tracing import configure_tracing, business_span, safe_span, SafeExporter, trace_response_headers


class MemoryExporter(SpanExporter):
    def __init__(self):
        self.spans = []
    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS
    def shutdown(self):
        pass


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


engine = create_engine('sqlite://')
down = FastAPI()
up = FastAPI()
memory = MemoryExporter()
os.environ['SECKILL_TRACING_ENABLED'] = 'true'
os.environ['SECKILL_TRACE_SAMPLE_RATIO'] = '1'
os.environ['OTEL_EXPORTER_OTLP_TRACES_ENDPOINT'] = 'http://127.0.0.1:1/v1/traces'
logs = io.StringIO()
handler = logging.StreamHandler(logs)
handler.addFilter(ContextFilter())
handler.setFormatter(JsonFormatter('test'))
logger = logging.getLogger('trace-harness')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

@business_span('inventory.reserve')
def reserve():
    with engine.connect() as connection:
        connection.execute(text("SELECT 'sensitive-sql-value'"))
    with patch.object(redis.Redis, '_execute_command', return_value='sensitive-redis-value'):
        redis.Redis().get('sensitive-redis-key')
    logger.info('reserved')
    return {'ok': True}

@down.get('/reserve')
def downstream():
    return reserve()

down_port, up_port = port(), port()

@up.get('/submit/{product_id}')
@business_span('order.submit')
def submit(product_id: int):
    response = httpx.get(f'http://127.0.0.1:{down_port}/reserve?token=sensitive-query')
    response.raise_for_status()
    return response.json()

@up.get('/error')
def error():
    raise RuntimeError('token=sensitive-exception')

@up.exception_handler(Exception)
async def error_response(request, exc):
    return JSONResponse({'error': 'failed'}, status_code=500, headers=trace_response_headers())

@up.get('/metrics')
def metrics():
    return {}

for app in (up, down):
    app.add_middleware(RequestContextMiddleware, record_http_request=lambda *args: None, logger=logger)
    provider = configure_tracing(app, 'test', (engine,))
provider.add_span_processor(BatchSpanProcessor(SafeExporter(memory), schedule_delay_millis=50))
servers = []
for app, p in ((up, up_port), (down, down_port)):
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=p, log_config=None, access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    servers.append((server, thread))
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started

# Entry requests deliberately use stdlib to avoid a client parent in the harness.
from urllib.request import urlopen
from urllib.error import HTTPError
start = time.monotonic()
for _ in range(6):
    with urlopen(f'http://127.0.0.1:{up_port}/submit/123') as response:
        assert response.status == 200
        trace_id = response.headers['X-Trace-ID']
assert time.monotonic() - start < 3, 'exporter outage blocked application requests'
with urlopen(f'http://127.0.0.1:{up_port}/metrics') as response:
    assert 'X-Trace-ID' not in response.headers
try:
    urlopen(f'http://127.0.0.1:{up_port}/error')
except HTTPError as exc:
    assert exc.code == 500
    assert len(exc.headers['X-Trace-ID']) == 32
provider.force_flush(4000)
spans = memory.spans
selected = [span for span in spans if format(span.context.trace_id, '032x') == trace_id]
names = [span.name for span in selected]
assert 'GET /submit/{product_id}' in names and 'GET /reserve' in names
assert 'order.submit' in names and 'inventory.reserve' in names
assert 'SELECT' in names and 'GET' in names
root = next(span for span in selected if span.name == 'GET /submit/{product_id}')
by_id = {span.context.span_id: span for span in selected}
child = next(span for span in selected if span.name == 'GET /reserve')
assert child.parent.span_id in by_id
assert by_id[child.parent.span_id].kind == trace.SpanKind.CLIENT
assert root.parent is None
assert root.attributes['seckill.outcome'] == 'success'
assert root.attributes['seckill.product_id'] == '123'
assert all(s.attributes.get('db.query.fingerprint') for s in selected if s.name == 'SELECT')
business = next(span for span in selected if span.name == 'order.submit')
assert business.attributes['seckill.product_id'] == '123'
assert business.attributes.get('seckill.request_id')
assert {event.name for event in business.events} == {'business.started', 'business.completed'}
encoded = json.dumps([{'name': s.name, 'attrs': dict(s.attributes), 'events': [str(e) for e in s.events], 'status': s.status.description} for s in spans])
assert 'sensitive-' not in encoded, encoded
assert all(span.name != 'GET /metrics' for span in spans)
records = [json.loads(line) for line in logs.getvalue().splitlines()]
assert any(record.get('trace_id') == trace_id and record.get('event') == 'http_access' for record in records)
assert not trace.get_current_span().get_span_context().is_valid
for server, thread in servers:
    server.should_exit = True
    thread.join(3)
provider.shutdown()
print(json.dumps({'requests': 6, 'spans_per_trace': len(selected), 'http_parent_link': True, 'outage_nonblocking': True, 'sanitized': True}))
