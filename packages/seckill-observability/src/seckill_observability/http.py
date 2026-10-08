from __future__ import annotations

import logging
import os
import random
import time

from .tracing import trace_fields
from .context import log_context, metric_method, metric_path, validate_request_id

_excluded = frozenset({"/metrics", "/health/live", "/health/ready"})


class RequestContextMiddleware:
    """Pure ASGI: keep context through sync endpoints, exceptions and streamed bodies."""

    def __init__(self, app, record_http_request, logger=None) -> None:
        self.app = app
        self.record_http_request = record_http_request
        self.logger = logger or logging.getLogger("seckill.http")
        self.enabled = os.getenv("SECKILL_OBSERVABILITY_ENABLED", "true").lower() != "false"
        self.access_log_ratio = float(os.getenv("SECKILL_ACCESS_LOG_SAMPLE_RATIO", "1"))
        if not 0 <= self.access_log_ratio <= 1:
            raise ValueError("SECKILL_ACCESS_LOG_SAMPLE_RATIO must be in [0, 1]")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        request_id = validate_request_id(headers.get(b"x-request-id", b"").decode("latin1"))
        scope.setdefault("state", {})["request_id"] = request_id
        start = time.perf_counter()
        status = 500
        failed = False

        async def contextual_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                from .tracing import business_attributes
                from opentelemetry import trace
                root = trace.get_current_span()
                for key, value in scope.get('path_params', {}).items():
                    if key in {'product_id', 'order_id', 'campaign_id'}:
                        business_attributes(root, value, key)
                root.set_attribute('seckill.outcome', 'error' if status >= 500 else 'rejected' if status >= 400 else 'success')
                message = {**message, "headers": [
                    (name, value) for name, value in message.get("headers", []) if name.lower() != b"x-request-id"
                ] + [(b"x-request-id", request_id.encode("ascii"))]}
            if message["type"] == "http.response.start" and trace_fields():
                message["headers"].append((b"x-trace-id", trace_fields()["trace_id"].encode("ascii")))
            await send(message)

        with log_context(request_id=request_id, **trace_fields()):
            from opentelemetry import trace
            trace.get_current_span().set_attribute('seckill.request_id', request_id)
            try:
                await self.app(scope, receive, contextual_send)
            except Exception:
                failed = True
                self.logger.exception("request failed", extra={"event": "http_request_failed", "route_template": metric_path(scope)})
                raise
            finally:
                if self.enabled and scope.get("path") not in _excluded:
                    duration = time.perf_counter() - start
                    path = metric_path(scope)
                    method = metric_method(scope.get("method", "OTHER"))
                    self.record_http_request(method, path, 500 if failed else status, duration)
                    from opentelemetry import trace
                    sampled_trace = trace.get_current_span().get_span_context().trace_flags.sampled
                    # Keep every rejection/error and every sampled trace's correlation log.
                    # Only successful, unrecorded access events may be sampled.
                    if failed or status >= 400 or sampled_trace or random.random() < self.access_log_ratio:
                        self.logger.info("request completed", extra={
                            "event": "http_access", "route_template": path, "method": method,
                            "status_code": 500 if failed else status, "duration_ms": round(duration * 1000, 2),
                        })
