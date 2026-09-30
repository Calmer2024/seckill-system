from prometheus_client import Counter, Histogram, generate_latest


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the service",
    ["service", "method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path"],
)


def record_http_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    HTTP_REQUESTS_TOTAL.labels("user", method, path, str(status)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels("user", method, path).observe(duration_seconds)


def metrics_payload() -> bytes:
    return generate_latest()
