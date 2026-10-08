"""Process-local tracing. Export is asynchronous, bounded and opt-in."""
from __future__ import annotations

import functools
import os
import socket
import inspect
import hashlib
import re
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider, Event
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Status, StatusCode
from prometheus_client import Counter

EXPORT_BATCHES = Counter("trace_export_batches_total", "Completed asynchronous trace export batches", ["result"])

SAFE_ATTRIBUTES = frozenset({
    "http.method", "http.request.method", "http.route", "http.status_code", "http.response.status_code",
    "db.system", "db.system.name", "db.name", "db.namespace", "db.operation", "db.operation.name",
    "messaging.system", "messaging.destination.name", "messaging.operation.type", "messaging.message.id",
    "messaging.consumer.group.name", "messaging.kafka.partition", "messaging.kafka.offset", "seckill.order_id", "seckill.attempt",
    "server.address", "server.port", "net.peer.name", "net.peer.port", "seckill.outcome", "seckill.error_code",
    "seckill.product_id", "seckill.campaign_id", "seckill.quantity", "seckill.request_id",
    "seckill.business_state", "seckill.entity", "seckill.causation_id", "seckill.queue_wait_ms",
    "seckill.mode", "exception.type", "seckill.result_count", "seckill.page", "seckill.page_size",
    "seckill.available_stock", "seckill.reserved_stock", "seckill.sold_stock", "db.query.fingerprint",
})
SAFE_EVENTS = frozenset({"business.started", "business.completed", "business.rejected", "business.failed",
                        "business.state_committed", "message.acked", "message.processed", "message.offset_committed"})
BUSINESS_STATES = frozenset({"CREATED", "PENDING_INVENTORY", "CONFIRMED", "REJECTED", "RESERVED", "PAID", "PAYING",
                           "SUCCESS", "PROCESSING", "FAILED", "CANCELED", "CANCELLED", "PUBLISHED", "RETRY"})


def business_attributes(span, value, name=''):
    """Only identifiers/quantity/state, never serialize a DTO or user identity."""
    for key in ('order_id', 'product_id', 'campaign_id', 'quantity'):
        field = value if name == key else value.get(key) if isinstance(value, dict) else getattr(value, key, None)
        if isinstance(field, int) and not isinstance(field, bool) and 0 < field <= 9223372036854775807:
            span.set_attribute('seckill.' + key, field if key == 'quantity' else str(field))
    for key in ('order_status', 'status'):
        state = value.get(key) if isinstance(value, dict) else getattr(value, key, None)
        if isinstance(state, str) and state in BUSINESS_STATES:
            span.set_attribute('seckill.business_state', state)
            break
    if isinstance(value, (list, tuple)):
        span.set_attribute('seckill.result_count', len(value))
    for key, target in (('page', 'page'), ('size', 'page_size'), ('limit', 'page_size'),
                        ('available_stock', 'available_stock'), ('reserved_stock', 'reserved_stock'), ('sold_stock', 'sold_stock')):
        field = value.get(key) if isinstance(value, dict) else getattr(value, key, None)
        if isinstance(field, int) and not isinstance(field, bool) and 0 <= field <= 9223372036854775807:
            span.set_attribute('seckill.' + target, field)


def service_version():
    configured = os.getenv('SERVICE_VERSION')
    if configured and configured != 'unknown':
        return configured[:160]
    try:
        return Path('/app/.observability-version').read_text(encoding='ascii').strip()[:160] or 'unknown'
    except OSError:
        return 'unknown'


def safe_span(span):
    attrs = {k: v for k, v in (span.attributes or {}).items() if k in SAFE_ATTRIBUTES}
    statement = (span.attributes or {}).get('db.statement') or (span.attributes or {}).get('db.query.text')
    if isinstance(statement, str) and len(statement) <= 32768 and (attrs.get('db.system') not in (None, 'redis') or attrs.get('db.system.name') not in (None, 'redis')):
        normalized = re.sub(r"'(?:''|[^'])*'|\b\d+(?:\.\d+)?\b", '?', statement)
        normalized = re.sub(r'\s+', ' ', normalized).strip().lower()
        attrs['db.query.fingerprint'] = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
    for key in ("db.operation", "db.operation.name"):
        if key in attrs:
            attrs[key] = str(attrs[key]).split(" ")[0][:24]
    name = span.name
    if span.kind == trace.SpanKind.SERVER:
        name = str(attrs.get("http.request.method", attrs.get("http.method", "HTTP"))) + " " + str(attrs.get("http.route", "__unmatched__"))
    elif attrs.get("db.system") or attrs.get("db.system.name"):
        # Library names can contain a Redis command's arguments or SQL database names.
        operation = str(name).split(" ")[0].upper()
        name = operation if operation.isalpha() and len(operation) < 24 else "DB"
    events = tuple(Event(event.name, {k: v for k, v in (event.attributes or {}).items() if k in SAFE_ATTRIBUTES},
                               event.timestamp) for event in span.events[-32:] if event.name in SAFE_EVENTS)
    return ReadableSpan(
        name=name, context=span.context, parent=span.parent, resource=span.resource,
        attributes=attrs, events=events, links=tuple(trace.Link(link.context, {"seckill.link.reason": link.attributes["seckill.link.reason"]})
            for link in (span.links or ())[:2] if (link.attributes or {}).get("seckill.link.reason") in {"delayed", "retry"}), kind=span.kind,
        status=Status(span.status.status_code), start_time=span.start_time, end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class SafeExporter(SpanExporter):
    """Allowlist before data leaves the process, including exception events."""
    def __init__(self, exporter):
        self.exporter = exporter

    def export(self, spans):
        from opentelemetry.sdk.trace.export import SpanExportResult
        try:
            result = self.exporter.export(tuple(safe_span(span) for span in spans))
        except Exception:
            # Exporter errors never escape into application processing.
            result = SpanExportResult.FAILURE
        EXPORT_BATCHES.labels("success" if result == SpanExportResult.SUCCESS else "failure").inc()
        return result

    def shutdown(self):
        self.exporter.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self.exporter.force_flush(timeout_millis)


_provider = None


def configure_tracing(app, service: str, engines=()):
    global _provider
    if os.getenv("SECKILL_OBSERVABILITY_ENABLED", "true").lower() == "false" or os.getenv("SECKILL_TRACING_ENABLED", "false").lower() != "true":
        return None
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    if _provider is None:
        ratio = float(os.getenv("SECKILL_TRACE_SAMPLE_RATIO", "0.1"))
        if not 0 <= ratio <= 1:
            raise ValueError("SECKILL_TRACE_SAMPLE_RATIO must be in [0, 1]")
        _provider = TracerProvider(resource=Resource({
            "service.name": service, "service.namespace": "seckill",
            "service.version": service_version(),
            "service.instance.id": os.getenv("SERVICE_INSTANCE_ID", socket.gethostname()) + ":" + str(os.getpid()),
            "deployment.environment.name": os.getenv("OBSERVABILITY_ENVIRONMENT", "local"),
        }), sampler=ParentBased(TraceIdRatioBased(ratio)))
        exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://otel-collector:4318/v1/traces"), timeout=1)
        _provider.add_span_processor(BatchSpanProcessor(SafeExporter(exporter), max_queue_size=2048,
            max_export_batch_size=256, schedule_delay_millis=1000, export_timeout_millis=1500))
        from opentelemetry import propagate
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        propagate.set_global_textmap(TraceContextTextMapPropagator())
        trace.set_tracer_provider(_provider)
        # The user service has no Redis dependency.
        import importlib.util
        if importlib.util.find_spec("httpx") is not None:
            HTTPXClientInstrumentor().instrument(tracer_provider=_provider)
        if importlib.util.find_spec("redis") is not None:
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            RedisInstrumentor().instrument(tracer_provider=_provider)
        SQLAlchemyInstrumentor().instrument(engines=list(engines), tracer_provider=_provider, enable_commenter=False)
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=_provider,
            excluded_urls=r"/metrics$,/health/live$,/health/ready$", exclude_spans=["receive", "send"])
    return _provider


def trace_fields():
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        return {"trace_id": format(context.trace_id, "032x"), "span_id": format(context.span_id, "016x")}
    return {}


def trace_response_headers():
    fields = trace_fields()
    return {"X-Trace-ID": fields["trace_id"]} if fields else {}


def business_span(name):
    def decorate(function):
        signature = inspect.signature(function)
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            parent = trace.get_current_span()
            server_parent = getattr(parent, 'kind', None) == trace.SpanKind.SERVER
            with trace.get_tracer("seckill.business").start_as_current_span(name,
                    record_exception=False, set_status_on_exception=False) as span:
                from .context import current_context
                context = current_context()
                if name.startswith(('order.', 'payment.', 'inventory.')):
                    span.set_attribute('seckill.entity', 'inventory' if name.startswith('inventory.') else 'order')
                if name == 'order.submit':
                    mode = os.getenv('ENABLE_KAFKA_ASYNC')
                    if mode is not None:
                        span.set_attribute('seckill.mode', 'distributed' if mode.lower() == 'true' else 'baseline')
                if context.get('request_id'):
                    span.set_attribute('seckill.request_id', context['request_id'])
                for key, value in signature.bind(*args, **kwargs).arguments.items():
                    business_attributes(span, value, key)
                    if server_parent:
                        business_attributes(parent, value, key)
                span.add_event('business.started')
                try:
                    result = function(*args, **kwargs)
                    business_attributes(span, result)
                    if server_parent:
                        business_attributes(parent, result)
                    if name.startswith('product.'):
                        business_attributes(span, getattr(result, 'id', None), 'product_id')
                        if server_parent:
                            business_attributes(parent, getattr(result, 'id', None), 'product_id')
                    span.set_attribute("seckill.outcome", "success")
                    span.add_event('business.completed', {k: v for k, v in (getattr(span, 'attributes', None) or {}).items() if k.startswith('seckill.')})
                    return result
                except Exception as exc:
                    code = getattr(exc, "status_code", 500)
                    span.set_attribute("seckill.outcome", "rejected" if isinstance(code, int) and code < 500 else "error")
                    error = getattr(exc, "code", None)
                    if isinstance(error, str) and error.replace("_", "").isalnum():
                        span.set_attribute("seckill.error_code", error[:64])
                    if not isinstance(code, int) or code >= 500:
                        span.set_status(Status(StatusCode.ERROR))
                        span.set_attribute('exception.type', type(exc).__name__[:100])
                    span.add_event('business.rejected' if isinstance(code, int) and code < 500 else 'business.failed',
                                   {k: v for k, v in (getattr(span, 'attributes', None) or {}).items() if k in SAFE_ATTRIBUTES})
                    raise
        return wrapped
    return decorate
