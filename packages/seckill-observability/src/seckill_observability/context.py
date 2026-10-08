from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator, Mapping

_context: ContextVar[dict] = ContextVar("seckill_log_context", default={})
_request_id = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_methods = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT", "TRACE"})


def validate_request_id(value: str | None) -> str:
    return value if value and _request_id.fullmatch(value) else uuid.uuid4().hex


def current_context() -> dict:
    return dict(_context.get())


@contextmanager
def log_context(**values) -> Iterator[None]:
    token = _context.set({**_context.get(), **{key: value for key, value in values.items() if value is not None}})
    try:
        yield
    finally:
        _context.reset(token)


def outbound_request_headers() -> dict[str, str]:
    value = _context.get().get("request_id")
    return {"X-Request-ID": value} if value else {}


def metric_method(method: str) -> str:
    return method if method in _methods else "OTHER"


def metric_path(scope: Mapping) -> str:
    # Never fall back to caller-controlled URL paths, including random 404s.
    return getattr(scope.get("route"), "path", None) or "__unmatched__"


def seckill_outcome(code: str) -> str:
    allowed = {
        "OUT_OF_STOCK": "out_of_stock", "DUPLICATE_ORDER": "duplicate",
        "PRODUCT_NOT_FOUND": "product_not_found", "STOCK_NOT_READY": "stock_not_ready",
        "INVENTORY_SERVICE_UNAVAILABLE": "inventory_service_unavailable",
        "INVENTORY_REQUEST_FAILED": "inventory_request_failed",
    }
    return allowed.get(code, "other")


def message_log_context(message) -> dict:
    """Business metadata only. Durable trace context is introduced in P2."""
    payload = message.value if isinstance(message.value, dict) else {}
    fields = {key: payload[key] for key in ("order_id", "product_id") if isinstance(payload.get(key), int)}
    return {**fields, "topic": message.topic, "partition": message.partition, "offset": message.offset}
