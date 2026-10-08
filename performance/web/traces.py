"""Bounded, read-only Tempo facade for the existing performance UI."""
from __future__ import annotations

import base64
import json
import os
import re
import shlex
import time
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
if __package__:
    from .trace_insights import analyze
else:
    from trace_insights import analyze
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERVICES = frozenset({"user", "product", "order-api", "inventory-api", "order-worker", "inventory-worker"})
ATTRIBUTES = frozenset({"http.method", "http.request.method", "http.route", "http.status_code", "http.response.status_code",
                       "db.system", "db.system.name", "db.name", "db.namespace", "db.operation", "db.operation.name",
                       "server.address", "server.port", "net.peer.name", "net.peer.port", "seckill.outcome", "seckill.error_code", "seckill.order_id", "seckill.attempt",
                       "messaging.system", "messaging.destination.name", "messaging.operation.type", "messaging.message.id",
                       "messaging.consumer.group.name", "messaging.kafka.partition", "messaging.kafka.offset"})
ATTRIBUTES = ATTRIBUTES | frozenset({'seckill.product_id', 'seckill.campaign_id', 'seckill.quantity', 'seckill.request_id',
    'seckill.business_state', 'seckill.entity', 'seckill.causation_id', 'seckill.queue_wait_ms', 'seckill.mode', 'exception.type',
    'seckill.result_count', 'seckill.page', 'seckill.page_size', 'seckill.available_stock', 'seckill.reserved_stock', 'seckill.sold_stock', 'db.query.fingerprint'})
EVENTS = frozenset({'business.started', 'business.completed', 'business.rejected', 'business.failed', 'business.state_committed',
                   'message.acked', 'message.processed', 'message.offset_committed'})
RESOURCES = frozenset({'service.name', 'service.version', 'service.instance.id', 'deployment.environment.name'})


class TraceUnavailable(Exception):
    pass


def read_tempo(path, *, health=False):
    endpoint = os.getenv("PERFORMANCE_TEMPO_URL", "http://127.0.0.1:3200").rstrip("/")
    try:
        with urlopen(Request(endpoint + path, headers={"Accept": "application/json"}), timeout=2.5) as response:
            body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise TraceUnavailable()
        return True if health else json.loads(body)
    except HTTPError as exc:
        if exc.code == 404 and not health:
            return None
        raise TraceUnavailable() from None
    except Exception:
        raise TraceUnavailable() from None


def trace_status():
    try:
        read_tempo("/ready", health=True)
        return "connected"
    except TraceUnavailable:
        return "unavailable"


_retention_cache = (0.0, 0)


def tempo_retention_seconds():
    """Read only the effective compactor retention, without exposing Tempo configuration."""
    global _retention_cache
    if _retention_cache[1] and time.monotonic() - _retention_cache[0] < 60:
        return _retention_cache[1]
    endpoint = os.getenv("PERFORMANCE_TEMPO_URL", "http://127.0.0.1:3200").rstrip("/")
    try:
        with urlopen(Request(endpoint + "/status/config"), timeout=2.5) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("oversized config")
        section = re.search(r"(?ms)^compactor:\s*\n(.*?)(?=^\S|\Z)", raw.decode("utf-8"))
        value = re.search(r"\bblock_retention:\s*([0-9dhms.]+)", section[1] if section else "")
        if not value or not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]+)?[dhms])+", value[1]):
            raise ValueError("missing retention")
        seconds = int(sum(float(n) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
                          for n, unit in re.findall(r"([0-9]+(?:\.[0-9]+)?)([dhms])", value[1])))
        if not 0 < seconds <= 366 * 86400:
            raise ValueError("invalid retention")
        _retention_cache = (time.monotonic(), seconds)
        return seconds
    except Exception:
        raise TraceUnavailable() from None


def search_window(params, now):
    """Explicit ranges, including retained history; never silently shorten a selected range."""
    window = params.get("window", ["15"])[0]
    if window == "custom":
        values = [params.get(key, [""])[0] for key in ("start", "end")]
        if not all(value.isdecimal() for value in values):
            raise ValueError("invalid dates")
        start, end = map(int, values)
        if not 0 < start < end <= now + 60:
            raise ValueError("invalid dates")
        return window, start, end
    if "start" in params or "end" in params:
        raise ValueError("dates require custom range")
    if window == "all":
        return window, 1, now
    # Legacy minute values remain compatible with existing callers.
    legacy = {"5": 300, "15": 900, "60": 3600}
    match = re.fullmatch(r"([1-9][0-9]{0,4})(m|h|d)", window)
    seconds = legacy.get(window)
    if match:
        seconds = int(match[1]) * {"m": 60, "h": 3600, "d": 86400}[match[2]]
    if seconds is None or not 60 <= seconds <= 30 * 86400:
        raise ValueError("invalid relative range")
    return window, max(1, now - seconds), now


def query_clauses(query, scope):
    """Translate a small documented field grammar into escaped, allowlisted TraceQL."""
    if len(query) > 512 or any(ord(c) < 32 for c in query) or scope not in {"root", "all"}:
        raise ValueError("invalid query")
    names = {"name": "trace:rootName" if scope == "root" else "name",
             "service": "trace:rootService" if scope == "root" else "resource.service.name",
             "order_id": "span.seckill.order_id", "event_id": "span.messaging.message.id",
             "error": "span.seckill.error_code", "method": "span.http.request.method",
             "route": "span.http.route", "db_system": "span.db.system",
             "topic": "span.messaging.destination.name", "outcome": "span.seckill.outcome"}
    names.update({'product_id': 'span.seckill.product_id', 'campaign_id': 'span.seckill.campaign_id',
                  'request_id': 'span.seckill.request_id', 'business_state': 'span.seckill.business_state',
                  'version': 'resource.service.version', 'instance': 'resource.service.instance.id',
                  'causation_id': 'span.seckill.causation_id'})
    clauses, free = [], []
    tokens = shlex.split(query)
    if len(tokens) > 16:
        raise ValueError("too many conditions")
    for token in tokens:
        if ":" not in token:
            free.append(token)
            continue
        field, value = token.split(":", 1)
        negative = field.startswith("-")
        field = field.lstrip("-")
        if not value or len(value) > 160:
            raise ValueError("missing field value")
        op = "!=" if negative else "="
        if field == "status":
            if value not in {"error", "ok", "unset"}:
                raise ValueError("invalid status")
            clauses.append("status " + op + " " + value)
        elif field == "trace_id":
            if not re.fullmatch(r"[0-9a-fA-F]{32}", value):
                raise ValueError("invalid trace id")
            clauses.append("trace:id " + op + " " + json.dumps(value.lower()))
        elif field in names:
            if field == "service" and value not in SERVICES:
                raise ValueError("invalid service")
            if field in {'order_id', 'product_id', 'campaign_id'} and (not re.fullmatch(r"[1-9][0-9]{0,18}", value) or int(value) > 9223372036854775807):
                raise ValueError("invalid order id")
            if field == "event_id" and not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
                raise ValueError("invalid event id")
            encoded = json.dumps(value.lower() if field == 'event_id' else value, ensure_ascii=False)
            aliases = {'method': ('span.http.request.method', 'span.http.method'),
                       'db_system': ('span.db.system', 'span.db.system.name')}
            if field in aliases:
                comparisons = [f'({key} != {encoded} && {key} != nil)' if negative else f'{key} = {encoded}' for key in aliases[field]]
                clauses.append('(' + ' || '.join(comparisons) + ')')
            else:
                clauses.append(names[field] + " " + op + " " + encoded)
        else:
            raise ValueError("unsupported query field")
    if free:
        text = " ".join(free)
        clauses.append(names["name"] + " =~ " + json.dumps(".*" + re.escape(text) + ".*", ensure_ascii=False))
    return clauses


def search_traces(params):
    # No raw TraceQL, backend URL, arbitrary tag, or unlimited result size.
    if set(params) - {"service", "services", "names", "window", "start", "end", "query", "query_scope", "min_duration_ms", "errors", "order_id", "event_id"}:
        raise ValueError("unsupported filter")
    service = params.get("service", [""])[0]
    selected_services = params.get("services", [])
    selected_names = params.get("names", [])
    if service and service not in SERVICES or len(selected_services) > 6 or any(s not in SERVICES for s in selected_services):
        raise ValueError("invalid service")
    if len(selected_names) > 8 or any(not n or len(n) > 160 for n in selected_names):
        raise ValueError("invalid names")
    now = int(time.time())
    window, start, end = search_window(params, now)
    minimum = params.get("min_duration_ms", ["0"])[0]
    if not minimum.isdecimal() or not 0 <= int(minimum) <= 60000:
        raise ValueError("invalid duration")
    errors = params.get("errors", ["false"])[0]
    if errors not in {"true", "false"}:
        raise ValueError("invalid error filter")
    clauses = ['resource.service.namespace = "seckill"', 'resource.deployment.environment.name = "local"']
    if service:
        clauses.append('resource.service.name = "' + service + '"')
    if selected_services:
        clauses.append("(" + " || ".join("resource.service.name = " + json.dumps(s) for s in selected_services) + ")")
    if selected_names:
        clauses.append("(" + " || ".join("trace:rootName = " + json.dumps(n, ensure_ascii=False) for n in selected_names) + ")")
    clauses.extend(query_clauses(params.get("query", [""])[0], params.get("query_scope", ["root"])[0]))
    if int(minimum):
        clauses.append("duration >= " + str(int(minimum)) + "ms")
    if errors == "true":
        clauses.append("status = error")
    order_id = params.get("order_id", [""])[0]
    event_id = params.get("event_id", [""])[0]
    if order_id:
        if not re.fullmatch(r"[1-9][0-9]{0,18}", order_id) or int(order_id) > 9223372036854775807:
            raise ValueError("invalid order id")
        clauses.append('span.seckill.order_id = "' + order_id + '"')
    if event_id:
        if not re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", event_id):
            raise ValueError("invalid event id")
        clauses.append('span.messaging.message.id = "' + event_id.lower() + '"')
    effective_start, effective_end, retention = start, end, None
    if window == "all" or end - start > 30 * 86400:
        retention = tempo_retention_seconds()
        effective_start = max(start, now - retention)
    # Tempo's default search limit is 7 days per request. Merge bounded chunks,
    # newest first, rather than changing the user's requested interval.
    found = {}
    cursor = effective_end
    while cursor > effective_start and len(found) < 50:
        chunk_start = max(effective_start, cursor - 7 * 86400)
        data = read_tempo("/api/search?" + urlencode({"q": "{ " + " && ".join(clauses) + " }", "start": chunk_start, "end": cursor, "limit": 50})) or {}
        for item in data.get("traces", [])[:50]:
            trace_id = str(item.get("traceID", ""))
            if re.fullmatch(r"[0-9a-fA-F]{32}", trace_id):
                found.setdefault(trace_id.lower(), item)
        cursor = chunk_start
    rows = []
    for item in list(found.values())[:50]:
        trace_id = str(item.get("traceID", ""))
        if not re.fullmatch(r"[0-9a-fA-F]{32}", trace_id):
            continue
        rows.append({"trace_id": trace_id.lower(), "service": str(item.get("rootServiceName", ""))[:64],
                     "name": str(item.get("rootTraceName", ""))[:160], "duration_ms": item.get("durationMs"),
                     "start_time_ns": item.get("startTimeUnixNano"),
                     # A search response does not establish success for the entire trace.
                     "status": "error" if errors == "true" else "unknown"})
    rows.sort(key=lambda item: int(item["start_time_ns"] or 0), reverse=True)
    return {"scope": "environment_live", "environment": "local", "window_minutes": (end - start) / 60,
            "window": window, "start": start, "end": end, "effective_start": effective_start,
            "retention_seconds": retention, "limit": 50,
            "sampled_at": now, "truncated": len(rows) >= 50, "traces": rows, "sampling_note": "只展示已采样链路；无结果不代表没有请求。"}


def attributes(items):
    result = {}
    for item in items or []:
        value = item.get("value", {})
        result[item.get("key")] = next((value[k] for k in ("stringValue", "intValue", "boolValue", "doubleValue") if k in value), None)
    return result


def hex_id(value, length):
    value = str(value or "")
    if re.fullmatch(r"[0-9a-fA-F]{" + str(length) + "}", value):
        return value.lower()
    try:
        raw = base64.b64decode(value, validate=True)
        return raw.hex() if len(raw) * 2 == length else ""
    except ValueError:
        return ""


def merge_spans(spans):
    """Tempo can return overlapping live/block fragments of the same span."""
    merged = {}
    for span in spans:
        if not span['span_id']:
            continue
        previous = merged.get(span['span_id'])
        if previous is None:
            merged[span['span_id']] = span
            continue
        # Prefer the richer fragment on conflicts, never drop complementary fields.
        older, richer = sorted((previous, span), key=lambda s: len(s['attributes']) + len(s.get('events', [])))
        node = {**older, **richer}
        node['attributes'] = {**older['attributes'], **richer['attributes']}
        node['resource'] = {**older.get('resource', {}), **richer.get('resource', {})}
        for key in node['resource']:
            if node['resource'][key] in ('unknown', ''):
                node['resource'][key] = next((s.get('resource', {}).get(key) for s in (richer, older)
                                             if s.get('resource', {}).get(key) not in (None, '', 'unknown')), node['resource'][key])
        events = {}
        for event in older.get('events', []) + richer.get('events', []):
            key = (event['name'], event['time_ns'])
            events[key] = {**event, 'attributes': {**events.get(key, {}).get('attributes', {}), **event['attributes']}}
        node['events'] = sorted(events.values(), key=lambda e: int(e['time_ns']))[:32]
        node['links'] = list({(l['trace_id'], l['span_id']): l for l in older.get('links', []) + richer.get('links', [])}.values())[:2]
        node['duration_ms'] = max(previous['duration_ms'], span['duration_ms'])
        node['parent_span_id'] = richer['parent_span_id'] or older['parent_span_id']
        if 'error' in (previous['status'], span['status']):
            node['status'] = 'error'
        elif 'ok' in (previous['status'], span['status']):
            node['status'] = 'ok'
        merged[span['span_id']] = node
    return list(merged.values())


def trace_detail(trace_id):
    if not re.fullmatch(r"[0-9a-f]{32}", trace_id):
        raise ValueError("invalid trace id")
    data = read_tempo("/api/traces/" + trace_id)
    if data is None:
        return None
    spans = []
    truncated = False
    for batch in data.get("batches", data.get("resourceSpans", [])):
        resource = attributes(batch.get("resource", {}).get("attributes", []))
        if resource.get("service.namespace") != "seckill" or resource.get("deployment.environment.name") != "local":
            continue
        for group in batch.get("scopeSpans", batch.get("instrumentationLibrarySpans", [])):
            for span in group.get("spans", []):
                if len(spans) >= 1000:
                    truncated = True
                    continue
                start, end = int(span.get("startTimeUnixNano", 0)), int(span.get("endTimeUnixNano", 0))
                spans.append({"span_id": hex_id(span.get("spanId"), 16), "parent_span_id": hex_id(span.get("parentSpanId"), 16),
                              "service": str(resource.get("service.name", "unknown"))[:64], "name": str(span.get("name", ""))[:160],
                              "kind": str(span.get("kind", "unknown")),
                              "resource": {k: str(v)[:160] for k, v in resource.items() if k in RESOURCES},
                              "events": [{'name': event['name'], 'time_ns': str(event.get('timeUnixNano', start)),
                                          'attributes': {k: v for k, v in attributes(event.get('attributes', [])).items() if k in ATTRIBUTES}}
                                         for event in span.get('events', [])[:32] if event.get('name') in EVENTS],
                              "links": [{"trace_id": hex_id(link.get("traceId"), 32), "span_id": hex_id(link.get("spanId"), 16),
                                         "reason": attributes(link.get("attributes", [])).get("seckill.link.reason", "related")}
                                        for link in span.get("links", [])[:2] if hex_id(link.get("traceId"), 32) and hex_id(link.get("spanId"), 16)],
                              "start_time_ns": str(start), "duration_ms": max(0, end-start)/1e6,
                              "status": {"2": "error", "STATUS_CODE_ERROR": "error", "1": "ok", "STATUS_CODE_OK": "ok"}.get(str(span.get("status", {}).get("code", "")), "unset"),
                              "attributes": {k: v for k, v in attributes(span.get("attributes", [])).items() if k in ATTRIBUTES}})
    # OTLP retry / replicated reads can return the same span more than once.
    spans = merge_spans(spans)
    spans.sort(key=lambda item: int(item["start_time_ns"]))
    return {"trace_id": trace_id, "spans": spans, "summary": summarize_trace(spans), "analysis": analyze(spans, truncated), "scope": "environment_live"} if spans else None


def summarize_trace(spans):
    """Protocol/business summaries; span UNSET alone is not evidence of success."""
    ids = {s['span_id'] for s in spans}
    roots = [s for s in spans if s['parent_span_id'] not in ids]
    root = next((s for s in roots if s.get('kind') in ('SPAN_KIND_SERVER', '2')), (roots or spans)[0])
    a = root['attributes']
    method = a.get('http.request.method', a.get('http.method', ''))
    route = a.get('http.route', '')
    input_parts = [method, route] if method or route else [a.get('db.operation.name', a.get('db.operation', '')),
                    a.get('messaging.operation.type', ''), a.get('messaging.destination.name', '')]
    code = a.get('http.response.status_code', a.get('http.status_code', ''))
    http_code = int(code) if str(code).isdigit() else 0
    outcomes = [s['attributes'].get('seckill.outcome') for s in spans]
    errors = list(dict.fromkeys(s['attributes']['seckill.error_code'] for s in spans if s['attributes'].get('seckill.error_code')))
    failed = [s for s in spans if s['status'] == 'error']
    state = ('error' if failed or http_code >= 500 or any(v in outcomes for v in ('error', 'failed')) else
             'rejected' if 400 <= http_code < 500 or 'rejected' in outcomes else
             'ok' if 200 <= http_code < 400 or any(v in outcomes for v in ('success', 'processed', 'duplicate')) else 'unknown')
    output = ([f'HTTP {http_code}'] if http_code else []) + errors
    outcome = next((v for v in ['error', 'failed', 'rejected', 'success', 'processed', 'duplicate'] if v in outcomes), '')
    if outcome:
        output.append(outcome)
    business = {k.split('.')[-1]: v for s in spans for k, v in s['attributes'].items() if k in
                {'seckill.order_id', 'seckill.product_id', 'seckill.campaign_id', 'seckill.quantity', 'seckill.business_state', 'seckill.request_id', 'seckill.result_count', 'seckill.page', 'seckill.page_size'}}
    for key, label in (('product_id', 'Product'), ('order_id', 'Order'), ('quantity', 'Quantity'), ('page', 'Page'), ('page_size', 'Size')):
        if key in business:
            input_parts.append(f'{label} {business[key]}')
    if 'result_count' in business:
        output.append(f"{business['result_count']} items")
    states = {}
    for span in spans:
        attrs = span['attributes']
        if attrs.get('seckill.entity') and attrs.get('seckill.business_state'):
            states[attrs['seckill.entity']] = attrs['seckill.business_state']
    if states:
        business['business_state'] = states.get('order', states.get('inventory'))
    if http_code == 202 and state == 'ok':
        state = 'accepted'
    state_reason = ('observed' if business.get('business_state') else
                    'not_created' if route == '/api/orders/seckill' and 'PRODUCT_NOT_FOUND' in errors else
                    'list_query' if 'result_count' in business else
                    'read_query' if method == 'GET' and not route.startswith('/api/orders/') else 'not_collected')
    api_result = 'accepted' if http_code == 202 else 'success' if 200 <= http_code < 400 else 'rejected' if 400 <= http_code < 500 else 'error' if http_code >= 500 else 'unknown'
    execution_type = ('api' if root.get('kind') in ('SPAN_KIND_SERVER', '2') or method else
                      'message' if root.get('kind') in ('SPAN_KIND_CONSUMER', '5', 'SPAN_KIND_PRODUCER', '4') or a.get('messaging.system') else
                      'task' if root.get('kind') in ('SPAN_KIND_INTERNAL', '1') else 'unknown')
    return {'status': state, 'api_result': api_result, 'business': business, 'business_state_reason': state_reason, 'entity_states': states, 'http_status': http_code or None,
            'execution_type': execution_type, 'services': sorted({s.get('service', 'unknown') for s in spans}), 'span_count': len(spans),
            'operations_truncated': len(spans) > 200,
            'operations': [{k: s.get(k) for k in ('span_id', 'parent_span_id', 'service', 'name', 'kind', 'status', 'duration_ms', 'start_time_ns')} for s in spans[:200]],
            'input': ' '.join(str(v) for v in input_parts if v) or '未采集输入摘要',
            'output': ' · '.join(output) or '未采集结果摘要',
            'error': ' · '.join(errors or [s['name'] for s in failed])}


_summary_cache = OrderedDict()
_summary_lock = threading.Lock()


def trace_summary(trace_id):
    if not re.fullmatch(r'[0-9a-fA-F]{32}', trace_id):
        raise ValueError('invalid trace ID')
    trace_id = trace_id.lower()
    with _summary_lock:
        entry = _summary_cache.get(trace_id)
        if entry and time.monotonic() - entry[0] < 20:
            _summary_cache.move_to_end(trace_id)
            return dict(entry[1])
    detail = trace_detail(trace_id)
    if detail is None:
        return None
    summary = detail['summary']
    with _summary_lock:
        _summary_cache[trace_id] = (time.monotonic(), summary)
        _summary_cache.move_to_end(trace_id)
        while len(_summary_cache) > 100:
            _summary_cache.popitem(last=False)
    return dict(summary)


def trace_lifecycle(params):
    """Bounded evidence timeline, not an order database/audit replacement."""
    if set(params) - {'order_id', 'event_id', 'window', 'start', 'end'} or any(len(v) != 1 for v in params.values()):
        raise ValueError('unsupported lifecycle filter')
    identifiers = [(key, params[key][0]) for key in ('order_id', 'event_id') if params.get(key, [''])[0]]
    if len(identifiers) != 1:
        raise ValueError('one lifecycle identifier required')
    key, value = identifiers[0]
    if key == 'event_id':
        value = value.lower()
    # Validate independently of Tempo availability; current database evidence survives a Trace outage.
    query_clauses(f'{key}:{value}', 'all')
    search_window(params, int(time.time()))
    evidence = order_evidence(value) if key == 'order_id' else {'availability': 'not_applicable'}
    trace_availability = 'available'
    try:
        search = search_traces({k: v for k, v in params.items() if k != key} | {'query': [f'{key}:{value}'], 'query_scope': ['all']})
    except TraceUnavailable:
        trace_availability = 'unavailable'
        search = {'traces': [], 'truncated': False, 'sampling_note': 'Trace backend unavailable; no absence conclusion can be drawn.'}
    rows = search['traces'][:20]
    def load(row):
        try:
            return trace_detail(row['trace_id'])
        except TraceUnavailable:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        details = list(pool.map(load, rows))
    timeline, executions = [], []
    for row, detail in zip(rows, details):
        if detail is None:
            continue
        spans = sorted(detail['spans'], key=lambda span: int(span['start_time_ns']))
        matched = lambda span: (span['attributes'].get('seckill.order_id') == value if key == 'order_id'
                                else span['attributes'].get('messaging.message.id') == value)
        executions.append({'trace_id': row['trace_id'], 'name': row.get('name'), 'service': row.get('service'),
                           'start_time_ns': spans[0]['start_time_ns'] if spans else row.get('start_time_ns'),
                           'duration_ms': row.get('duration_ms'),
                           'summary': detail.get('summary') or summarize_trace(spans),
                           'spans': [dict(span, identifier_match=matched(span)) for span in spans[:200]],
                           'spans_truncated': len(spans) > 200 or bool(detail.get('analysis', {}).get('quality', {}).get('truncated')),
                           'span_limit': 200, 'matched_span_count': sum(matched(span) for span in spans)})
        for span in detail['spans']:
            a = span['attributes']
            if not (a.get('seckill.order_id') == value if key == 'order_id' else a.get('messaging.message.id') == value):
                continue
            timeline.append({'trace_id': row['trace_id'], 'span_id': span['span_id'], 'time_ns': span['start_time_ns'],
                             'parent_span_id': span['parent_span_id'], 'kind': span['kind'], 'attributes': a,
                             'name': span['name'], 'service': span['service'], 'duration_ms': span['duration_ms'],
                             'state': a.get('seckill.business_state'), 'outcome': a.get('seckill.outcome'),
                             'event_id': a.get('messaging.message.id'), 'causation_id': a.get('seckill.causation_id'),
                             'attempt': a.get('seckill.attempt'), 'queue_wait_ms': a.get('seckill.queue_wait_ms'),
                             'events': span.get('events', [])[:8], 'links': span['links']})
    timeline.sort(key=lambda node: int(node['time_ns']))
    executions.sort(key=lambda execution: int(execution['start_time_ns'] or 0))
    return {'identifier': {key: value}, 'timeline': timeline[:300], 'trace_count': len(rows),
            'executions': executions, 'business_evidence': evidence, 'trace_availability': trace_availability,
            'unavailable_traces': sum(d is None for d in details), 'truncated': search['truncated'] or len(search['traces']) > 20 or len(timeline) > 300 or any(e['spans_truncated'] for e in executions),
            'sampling_note': search['sampling_note'], 'authoritative_order_state': evidence.get('availability') == 'available' and evidence.get('found', False)}


def order_evidence(order_id):
    """Fixed localhost adapter for the SELECT-only audit service; never use business credentials."""
    try:
        with urlopen('http://127.0.0.1:9124/orders/' + order_id, timeout=3) as response:
            body = response.read(128 * 1024 + 1)
        if len(body) > 128 * 1024:
            raise ValueError('oversized evidence')
        return json.loads(body)
    except (OSError, ValueError):
        return {'availability': 'unavailable', 'source': 'mysql_primary_read_only'}


def search_orders(params):
    if set(params) - {'window', 'start', 'end', 'status', 'order_id', 'product_id', 'before'} or any(len(v)!=1 for v in params.values()):
        raise ValueError('invalid order filters')
    _, start, end = search_window(params, int(time.time()))
    query = {'start': str(start), 'end': str(end)}
    statuses = {'CREATED','SUCCESS','PENDING_INVENTORY','CONFIRMED','REJECTED','PAYING','PAID','CANCELED','CANCELLED','FAILED'}
    for key in ('status', 'order_id', 'product_id', 'before'):
        value = params.get(key, [''])[0]
        if value:
            if key == 'status':
                if value not in statuses:
                    raise ValueError('invalid status')
            elif not re.fullmatch('[1-9][0-9]{0,18}', value) or int(value) > 9223372036854775807:
                raise ValueError('invalid identifier')
            query[key] = value
    try:
        with urlopen('http://127.0.0.1:9124/orders?' + urlencode(query), timeout=8) as response:
            body = response.read(128 * 1024 + 1)
        if len(body) > 128 * 1024:
            raise ValueError('oversized order list')
        return json.loads(body)
    except (OSError, ValueError):
        raise TraceUnavailable() from None
