"""Fixed-backend, bounded read facades for logs, environment charts and alerts."""
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERVICES = {"user": "user_service", "product": "product_service_[12]", "order-api": "order_service", "inventory-api": "inventory_service", "order-worker": "order_worker", "inventory-worker": "inventory_worker", "gateway": "frontend_nginx"}
FIELDS = {"timestamp", "level", "logger", "message", "exception", "event", "request_id", "trace_id", "span_id", "order_id", "product_id", "event_id", "causation_id", "topic", "partition", "offset", "group", "attempt", "outcome", "error_code", "status_code", "route_template", "method", "duration_seconds", "duration_ms", "upstream", "upstream_status", "upstream_seconds", "role", "from_status", "to_status", "order_status", "payment_status", "outbox_record_id"}


class SignalUnavailable(Exception):
    pass


def read(backend, path):
    urls = {"loki": ("PERFORMANCE_LOKI_URL", "http://127.0.0.1:3100"), "prometheus": ("PERFORMANCE_PROMETHEUS_URL", "http://127.0.0.1:9090"),
            "alerts": ("PERFORMANCE_ALERTMANAGER_URL", "http://127.0.0.1:9093"), "notifications": ("PERFORMANCE_ALERT_RECEIVER_URL", "http://127.0.0.1:9122")}
    setting, default = urls[backend]
    try:
        with urlopen(Request(os.getenv(setting, default).rstrip("/") + path, headers={"Accept": "application/json"}), timeout=2.5) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError()
        return json.loads(body)
    except Exception:
        raise SignalUnavailable() from None


def filters(params, allowed):
    if set(params) - allowed or any(len(v) != 1 for v in params.values()):
        raise ValueError("unsupported filter")
    window = params.get("window", ["15"])[0]
    if window not in {"5", "15", "60", "180", "360", "720", "1440", "2880", "10080", "20160", "43200"}:
        raise ValueError("invalid window")
    return int(window)


def redact(value):
    text = str(value)[:8192]
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", text)
    text = re.sub(r'''(?i)((?:password|passwd|pwd|secret|token|authorization|cookie|api_key)["' ]*[:=]["' ]*)[^"'\s,}]+''', r"\1[REDACTED]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED]", text)
    return text


def explicit_range(params, now):
    if "start" not in params and "end" not in params:
        return None
    values = [params.get(key, [""])[0] for key in ("start", "end")]
    if not all(value.isdecimal() for value in values):
        raise ValueError("invalid dates")
    start, end = map(int, values)
    if not 0 < start < end <= now + 60 or end - start > 30 * 86400:
        raise ValueError("invalid dates")
    return start, end


def search_logs(params):
    window = filters(params, {"service", "window", "level", "trace_id", "order_id", "event_id", "request_id", "text", "at", "start", "end"})
    service = params.get("service", [""])[0]
    level = params.get("level", [""])[0]
    if service and service not in SERVICES or level not in {"", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("invalid service or level")
    selector = '{namespace="seckill",environment="local"'
    if service:
        selector += ',service=~' + json.dumps(SERVICES[service])
    query = selector + '} | json | __error__=""'
    for name, pattern in (("trace_id", r"[0-9a-fA-F]{32}"), ("order_id", r"[1-9][0-9]{0,18}"), ("event_id", r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"), ("request_id", r"[A-Za-z0-9._-]{1,64}")):
        value = params.get(name, [""])[0]
        if value:
            if not re.fullmatch(pattern, value) or name == "order_id" and int(value) > 9223372036854775807:
                raise ValueError("invalid id")
            query += " | " + name + "=" + json.dumps(value.lower() if name in {"trace_id", "event_id"} else value)
    if level:
        query += " | level=" + json.dumps(level)
    text = params.get("text", [""])[0]
    if len(text) > 80 or any(ord(char) < 32 for char in text):
        raise ValueError("invalid text")
    if text:
        # Literal substring; JSON escaping forbids injecting LogQL stages.
        query += " |= " + json.dumps(text)
    now = int(time.time())
    end = now
    anchor = params.get("at", [""])[0]
    if anchor:
        if not params.get("trace_id", [""])[0] or not anchor.isdecimal() or not now - 72 * 3600 <= int(anchor) <= now:
            raise ValueError("invalid anchor")
        end = min(now, int(anchor) + window * 30)
    custom = explicit_range(params, now)
    if custom and anchor:
        raise ValueError("dates conflict with anchor")
    start, end = custom or (end - window * 60, end)
    data = read("loki", "/loki/api/v1/query_range?" + urlencode({"query": query, "start": start * 10**9, "end": end * 10**9, "limit": 200, "direction": "backward"}))
    if data.get("status") != "success":
        raise SignalUnavailable()
    rows = []
    reverse = {v: k for k, v in SERVICES.items() if "[" not in v}
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        for timestamp, line, *_ in stream.get("values", []):
            try:
                parsed = json.loads(line)
                if not isinstance(parsed, dict) or not str(timestamp).isdecimal():
                    continue
                fields = {k: redact(v) for k, v in parsed.items() if k in FIELDS and isinstance(v, (str, int, float, bool))}
                fields["trace_id"] = fields.get("trace_id", "") if re.fullmatch(r"[0-9a-f]{32}", fields.get("trace_id", "")) else ""
                instance = str(labels.get("instance", ""))[:100]
                source = labels.get("service", "")
                rows.append({"timestamp_ns": str(timestamp), "service": "product" if re.fullmatch(r"product_service_[12]", source) else reverse.get(source, "unknown"), "instance": instance, "fields": fields})
            except (ValueError, TypeError):
                continue
    rows.sort(key=lambda row: int(row["timestamp_ns"]), reverse=True)
    return {"scope": "environment_live", "environment": "local", "sampled_at": now, "window_minutes": window, "limit": 200, "logs": rows[:200], "truncated": len(rows) >= 200}


CHARTS = {
    "http_rate": ("请求速率", "req/s", 'sum by (service) (rate(http_requests_total{service=~"user|product|order|inventory"}[2m]))'),
    "http_p95": ("HTTP p95", "s", 'histogram_quantile(0.95,sum by (le,service) (rate(http_request_duration_seconds_bucket[2m])))'),
    "kafka_lag": ("Kafka 消费积压", "条", 'sum by (consumergroup,topic) (clamp_min(kafka_consumergroup_lag{consumergroup=~"seckill-inventory-order-created|seckill-order-inventory-result|seckill-order-payment",topic=~"seckill-order-created-topic|seckill-inventory-result-topic|seckill-payment-topic"},0))'),
    "db_connections": ("MySQL 当前连接", "个", 'mysql_global_status_threads_connected'),
    "outbox_pending": ("Outbox 待发布", "条", 'observability_business_outbox_pending_events'),
    "negative_stock": ("负库存商品", "个", 'observability_business_inventory_negative_items'),
    "slo_burn_fast": ("HTTP 错误预算消耗 · 5 分钟", "倍", 'seckill:api_error_ratio:5m / 0.001'),
    "slo_burn_slow": ("HTTP 错误预算消耗 · 6 小时", "倍", 'seckill:api_error_ratio:6h / 0.001'),
}


def chart(key, end, window, start=None):
    title, unit, query = CHARTS[key]
    try:
        start = end - window * 60 if start is None else start
        data = read("prometheus", "/api/v1/query_range?" + urlencode({"query": query, "start": start, "end": end, "step": max(5, math.ceil((end - start) / 120))}))
        if data.get("status") != "success":
            raise SignalUnavailable()
        series = []
        for item in data["data"].get("result", [])[:16]:
            points = []
            for timestamp, value in item.get("values", [])[:121]:
                number = float(value)
                points.append([timestamp, number if math.isfinite(number) else None])
            series.append({"labels": {k: ({"order":"order-api","inventory":"inventory-api"}.get(str(v),str(v)) if k == "service" else str(v))[:100] for k, v in item["metric"].items() if k in {"service", "instance", "owner", "topic", "consumergroup"}}, "points": points})
        return {"id": key, "title": title, "unit": unit, "status": "ok" if series else "missing", "series": series}
    except (SignalUnavailable, ValueError, TypeError, KeyError):
        return {"id": key, "title": title, "unit": unit, "status": "unavailable", "series": []}


def metrics(params):
    window = filters(params, {"window", "start", "end"})
    now = int(time.time())
    start, end = explicit_range(params, now) or (now - window * 60, now)
    with ThreadPoolExecutor(max_workers=4) as executor:
        charts = list(executor.map(lambda key: chart(key, end, window, start), CHARTS))
    # DB audit gauges are cached last evidence; a successful Prometheus read is not freshness.
    try:
        data = read("prometheus", "/api/v1/query?" + urlencode({"query": 'observability_business_collection_success == 1 and on() (time() - max(observability_business_last_success_timestamp_seconds) < 90)'}))
        fresh = data.get("status") == "success" and bool(data.get("data", {}).get("result"))
    except SignalUnavailable:
        fresh = False
    if not fresh:
        for item in charts:
            if item["id"] in {"outbox_pending", "negative_stock"} and "start" not in params:
                item.update(status="stale", series=[])
    return {"scope": "environment_live", "sampled_at": now, "window_minutes": window, "start": start, "end": end, "charts": charts, "business_evidence_fresh": fresh}


def alerts(params):
    if params:
        raise ValueError("unsupported filter")
    result = {"sampled_at": int(time.time()), "alerts": [], "notifications": [], "alert_status": "unavailable", "notification_status": "unavailable"}
    try:
        payload = read("alerts", "/api/v2/alerts?active=true&silenced=false&inhibited=false")
        if not isinstance(payload, list):
            raise SignalUnavailable()
        result["alerts"] = [{"labels": {k: redact(v)[:160] for k, v in item.get("labels", {}).items()}, "annotations": {k: redact(v)[:1000] for k, v in item.get("annotations", {}).items() if k in {"summary", "description", "runbook_url"}}, "starts_at": item.get("startsAt")} for item in payload[:100] if item.get("labels", {}).get("environment") == "local"]
        result["alert_status"] = "ok"
    except SignalUnavailable:
        pass
    try:
        payload = read("notifications", "/events")
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise SignalUnavailable()
        result["notifications"] = payload["events"][:100]
        result["notification_status"] = "ok"
    except SignalUnavailable:
        pass
    return result
