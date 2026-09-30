from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, multiprocess


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
PRODUCT_CACHE_OPERATIONS_TOTAL = Counter(
    "product_cache_operations_total",
    "Product cache operations",
    ["operation", "result"],
)
PRODUCT_DB_READS_TOTAL = Counter(
    "product_db_reads_total",
    "Product database reads",
    ["operation", "outcome"],
)


def record_http_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    HTTP_REQUESTS_TOTAL.labels("product", method, path, str(status)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels("product", method, path).observe(duration_seconds)


def metrics_payload() -> bytes:
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return generate_latest(registry)
