from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import socket
import sys
from datetime import datetime, timezone

from .context import current_context

_fields = (
    "event", "request_id", "trace_id", "span_id", "route_template", "method", "status_code",
    "duration_ms", "order_id", "product_id", "event_id", "causation_id", "topic", "partition",
    "offset", "group", "attempt", "outbox_record_id", "outcome", "error_code", "order_status", "payment_status",
    "from_status", "to_status", "role", "db_role", "read_database", "write_database", "page", "size", "count",
)
_secrets = re.compile(r'''(?i)((?:["']?)(?:password|passwd|pwd|secret|token|authorization|cookie|api[_-]?key)(?:["']?)\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)''')
_bearer = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+")
_dsn = re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.-]*://)[^\s/@]+:[^\s/@]+@")
_email = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_phone = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_query = re.compile(r"(https?://[^\s?]+)\?[^\s]+")


def redact(value: str) -> str:
    value = _dsn.sub(r"\1[REDACTED]@", value)
    value = _bearer.sub("Bearer [REDACTED]", value)
    value = _secrets.sub(r"\1[REDACTED]", value)
    value = _email.sub("[EMAIL]", value)
    value = _phone.sub("[PHONE]", value)
    return _query.sub(r"\1?[REDACTED]", value)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        from .tracing import trace_fields
        record.observability_context = {**current_context(), **trace_fields()}
        return True


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str = "unknown") -> None:
        super().__init__()
        from .tracing import service_version
        self.resource = {
            "schema_version": 1, "namespace": "seckill", "service": service,
            "environment": os.getenv("OBSERVABILITY_ENVIRONMENT", "local"),
            "version": service_version(),
            "instance": os.getenv("SERVICE_INSTANCE_ID", socket.gethostname()),
        }
        self.user_hash_key = os.getenv("LOG_USER_ID_HASH_KEY")

    def format(self, record: logging.LogRecord) -> str:
        context = getattr(record, "observability_context", current_context())
        payload = {
            **self.resource, "process_id": record.process,
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname, "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for name in _fields:
            value = getattr(record, name, context.get(name))
            if value is not None and isinstance(value, (str, int, float, bool)):
                payload[name] = redact(value)[:512] if isinstance(value, str) else value
        # Raw URL, keyword, cache key, request bodies and credentials are not schema fields.
        if self.user_hash_key and getattr(record, "user_id", None) is not None:
            payload["user_hash"] = hmac.new(self.user_hash_key.encode(), str(record.user_id).encode(), hashlib.sha256).hexdigest()
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, allow_nan=False)


def configure_logging(level: str = "INFO", service: str | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter(service or os.getenv("OBSERVABILITY_SERVICE_NAME", "unknown")))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper() if os.getenv("SECKILL_OBSERVABILITY_ENABLED", "true").lower() != "false" else "ERROR")
    # Uvicorn's own handlers would otherwise bypass the schema and duplicate access logs.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)


get_logger = logging.getLogger
