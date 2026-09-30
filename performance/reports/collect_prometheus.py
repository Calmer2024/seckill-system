from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


QUERIES = {
    "http_rps": 'sum(rate(http_requests_total[5m]))',
    "http_p50_seconds": 'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
    "http_p95_seconds": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
    "http_p99_seconds": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
    "http_error_rate": '(sum(rate(http_requests_total{status=~"4..|5.."}[5m])) or vector(0)) / clamp_min(sum(rate(http_requests_total[5m])), 1)',
    "product_cache_hit_rate": '(sum(rate(product_cache_operations_total{operation="get",result="hit"}[5m])) or vector(0)) / clamp_min(sum(rate(product_cache_operations_total{operation="get"}[5m])), 1)',
    "redis_connected_clients": "redis_connected_clients",
    "mysql_threads_connected": "mysql_global_status_threads_connected",
    "mysql_slow_queries": "rate(mysql_global_status_slow_queries[5m])",
    "mysql_row_lock_waits": "mysql_global_status_innodb_row_lock_waits",
    "mysql_row_lock_time_ms": "mysql_global_status_innodb_row_lock_time",
    "mysql_replica_lag_seconds": 'mysql_slave_status_seconds_behind_master{job="mysql_replica"}',
    "kafka_max_lag": "max(kafka_consumergroup_lag)",
    "order_outbox_pending": 'performance_outbox_pending{service="order"}',
    "inventory_outbox_pending": 'performance_outbox_pending{service="inventory"}',
    "order_outbox_peak": 'performance_outbox_pending_peak{service="order"}',
    "inventory_outbox_peak": 'performance_outbox_pending_peak{service="inventory"}',
    "inventory_available": 'performance_inventory_stock{state="available"}',
    "inventory_reserved": 'performance_inventory_stock{state="reserved"}',
    "inventory_sold": 'performance_inventory_stock{state="sold"}',
    "valid_orders": "performance_valid_order_total",
    "state_converged": "performance_state_converged",
    "duplicate_order_groups": "performance_duplicate_order_groups",
}

PEAK_QUERIES = {
    "kafka_peak_lag": "max(kafka_consumergroup_lag)",
    "order_outbox_peak_during_run": 'performance_outbox_pending{service="order"}',
    "inventory_outbox_peak_during_run": 'performance_outbox_pending{service="inventory"}',
    "http_rps_peak": "sum(rate(http_requests_total[1m]))",
    "container_cpu_peak_cores": 'sum(rate(container_cpu_usage_seconds_total{id=~"/docker/[a-f0-9]+"}[1m]))',
    "container_memory_peak_bytes": 'sum(container_memory_working_set_bytes{id=~"/docker/[a-f0-9]+"})',
}

BUSINESS_METRICS = {
    "order_outbox_pending", "inventory_outbox_pending", "order_outbox_peak",
    "inventory_outbox_peak", "inventory_available", "inventory_reserved",
    "inventory_sold", "valid_orders", "state_converged", "duplicate_order_groups",
    "order_outbox_peak_during_run", "inventory_outbox_peak_during_run",
}

BASELINE_INACTIVE = {"product_cache_hit_rate", "kafka_max_lag", "kafka_peak_lag"}
PRODUCT_READ_INACTIVE = {"kafka_max_lag", "kafka_peak_lag"}


def query(prometheus_url: str, expression: str) -> float | None:
    url = f"{prometheus_url.rstrip('/')}/api/v1/query?{urllib.parse.urlencode({'query': expression})}"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("data", {}).get("result", [])
    if not results:
        return None
    try:
        value = float(results[0]["value"][1])
        return value if math.isfinite(value) else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def query_range_max(
    prometheus_url: str,
    expression: str,
    start_time: int,
    end_time: int,
    step_seconds: int = 5,
) -> float | None:
    params = {
        "query": expression,
        "start": start_time,
        "end": end_time,
        "step": step_seconds,
    }
    url = f"{prometheus_url.rstrip('/')}/api/v1/query_range?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    samples = []
    for result in payload.get("data", {}).get("result", []):
        for _, value in result.get("values", []):
            try:
                number = float(value)
                if math.isfinite(number):
                    samples.append(number)
            except (TypeError, ValueError):
                continue
    return max(samples) if samples else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect end-of-run values from Prometheus.")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--output", required=True)
    parser.add_argument("--start-time", type=int)
    parser.add_argument("--mode", choices=("baseline", "distributed"), default="distributed")
    parser.add_argument("--scenario", default="product-read")
    args = parser.parse_args()

    metrics = {}
    errors = []
    peaks = {}
    end_time = int(time.time())
    for name, expression in QUERIES.items():
        try:
            metrics[name] = query(args.prometheus_url, expression)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            errors.append(f"{name}: {exc}")
            metrics[name] = None

    if args.start_time is not None:
        for name, expression in PEAK_QUERIES.items():
            try:
                peaks[name] = query_range_max(
                    args.prometheus_url,
                    expression,
                    args.start_time,
                    end_time,
                )
            except (OSError, urllib.error.URLError, TimeoutError) as exc:
                errors.append(f"{name}: {exc}")
                peaks[name] = None

    try:
        business_healthy = query(args.prometheus_url, "performance_business_collector_errors") == 0
    except (OSError, urllib.error.URLError, TimeoutError):
        business_healthy = False
    try:
        mysql_healthy = query(args.prometheus_url, 'up{job="mysql"}') == 1
    except (OSError, urllib.error.URLError, TimeoutError):
        mysql_healthy = False
    try:
        replica_healthy = query(args.prometheus_url, 'up{job="mysql_replica"}') == 1
    except (OSError, urllib.error.URLError, TimeoutError):
        replica_healthy = False

    statuses = {}
    for name, value in {**metrics, **peaks}.items():
        if (args.mode == "baseline" and name in BASELINE_INACTIVE) or (args.scenario == "product-read" and name in PRODUCT_READ_INACTIVE):
            statuses[name] = "not_applicable"
        elif name in BUSINESS_METRICS and not business_healthy:
            statuses[name] = "collector_error"
        elif name.startswith("mysql_") and not (replica_healthy if name == "mysql_replica_lag_seconds" else mysql_healthy):
            statuses[name] = "collector_error"
        else:
            statuses[name] = "ok" if value is not None else "missing"
        if statuses[name] != "ok":
            if name in metrics:
                metrics[name] = None
            else:
                peaks[name] = None

    result = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "prometheus_url": args.prometheus_url,
        "metrics": metrics,
        "peaks_during_run": peaks,
        "metric_status": statuses,
        "sources": {"business": business_healthy, "mysql": mysql_healthy, "mysql_replica": replica_healthy},
        "errors": errors,
        "available": not errors and all(status in ("ok", "not_applicable") for status in statuses.values()),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"available": result["available"], "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
