"""Read-only, bounded P0 status adapter for the local performance workspace.

No caller-supplied URLs or queries; no run snapshot is fabricated from live data.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROMETHEUS_URL = os.getenv("PERFORMANCE_PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/")
EXPECTED = {
    "user_service": ("user", "API", ()),
    "product_service": ("product", "API", ()),
    "order_service": ("order-api", "API", ()),
    "inventory_service": ("inventory-api", "API", ()),
    "order_worker": ("order-worker", "worker", ("order-outbox-publisher", "inventory-result-consumer", "payment-result-consumer")),
    "inventory_worker": ("inventory-worker", "worker", ("inventory-outbox-publisher", "inventory-order-created-consumer")),
    "otel_collector": ("otel-collector", "telemetry", ()),
    "tempo": ("tempo", "telemetry", ()),
    "loki": ("loki", "telemetry", ()),
    "alloy": ("alloy", "telemetry", ()),
    "alertmanager": ("alertmanager", "telemetry", ()),
    "business_audit": ("business-audit", "audit", ()),
    "alert_receiver": ("alert-receiver", "telemetry", ()),
}
QUERY = '{__name__=~"worker_task_alive|worker_loop_last_poll_timestamp_seconds|worker_loop_last_progress_timestamp_seconds|worker_task_failures_total",job=~"order_worker|inventory_worker"}'
_cache_lock = threading.Lock()
_cache: dict | None = None
_expires = 0.0


def read_prometheus(path: str) -> dict:
    request = Request(PROMETHEUS_URL + path, headers={"Accept": "application/json"})
    with urlopen(request, timeout=2.5) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("Prometheus response exceeds limit")
    payload = json.loads(body)
    if payload.get("status") != "success":
        raise ValueError("Prometheus query failed")
    return payload["data"]


def finite_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def sample_age(scraped_at: str | None, now: float) -> float | None:
    try:
        return max(0, now - datetime.fromisoformat(scraped_at.replace("Z", "+00:00")).timestamp())
    except (AttributeError, ValueError):
        return None


def build_status(target_data: dict | None, metric_data: dict | None, now: float, errors: list[str]) -> dict:
    metrics = {}
    for sample in (metric_data or {}).get("result", []):
        labels = sample.get("metric", {})
        value = sample.get("value", [None, None])
        number = finite_number(value[1])
        if number is not None:
            metrics[(labels.get("job"), labels.get("instance"), labels.get("role"), labels.get("__name__"))] = number
    targets = (target_data or {}).get("activeTargets", [])
    services = []
    for job, (name, kind, roles) in EXPECTED.items():
        matches = [item for item in targets if item.get("labels", {}).get("job") == job]
        if not matches:
            missing = "unavailable" if target_data is None else "not_configured"
            services.append({"service": name, "kind": kind, "instance": None,
                             "status": missing, "tasks": [{"role": role, "status": missing,
                                 "alive": None, "poll_age_seconds": None,
                                 "progress_age_seconds": None, "failures": None} for role in roles]})
            continue
        for target in matches:
            instance = target.get("labels", {}).get("instance")
            age = sample_age(target.get("lastScrape"), now)
            fresh = target.get("health") == "up" and age is not None and age <= 30
            status = "up" if fresh else "down" if target.get("health") == "down" else "stale"
            tasks = []
            for role in roles:
                values = {key: metrics.get((job, instance, role, key)) for key in (
                    "worker_task_alive", "worker_loop_last_poll_timestamp_seconds",
                    "worker_loop_last_progress_timestamp_seconds", "worker_task_failures_total",
                )}
                alive = values["worker_task_alive"] if fresh and metric_data is not None else None
                poll = values["worker_loop_last_poll_timestamp_seconds"]
                progress = values["worker_loop_last_progress_timestamp_seconds"]
                task_status = "unavailable" if not fresh or metric_data is None else "not_instrumented" if alive is None else "down" if alive == 0 else "stalled" if not poll or now - poll > 90 else "up"
                tasks.append({"role": role, "status": task_status, "alive": alive,
                              "poll_age_seconds": max(0, now - poll) if fresh and poll else None,
                              "progress_age_seconds": max(0, now - progress) if fresh and progress else None,
                              "failures": values["worker_task_failures_total"] if fresh else None})
            if tasks and any(item["status"] in {"down", "stalled"} for item in tasks):
                status = "degraded"
            elif tasks and fresh and any(item["status"] == "not_instrumented" for item in tasks):
                status = "not_instrumented"
            elif tasks and fresh and metric_data is None:
                status = "partial"
            services.append({"service": name, "kind": kind, "instance": instance, "status": status,
                             "last_scrape": target.get("lastScrape"), "sample_age_seconds": age,
                             "tasks": tasks})
    return {
        "scope": "environment_live", "environment": "local", "sampled_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "source": "Prometheus", "status": "unavailable" if target_data is None else "partial" if errors else "ok",
        "errors": errors, "services": services,
        "capabilities": {"metrics": "configured", "traces": "not_connected", "centralized_logs": "not_connected"},
    }


def collect_status() -> dict:
    results = []
    errors = []
    paths = ("/api/v1/targets", "/api/v1/query?" + urlencode({"query": QUERY}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(read_prometheus, path) for path in paths]
        for label, future in zip(("targets", "worker_metrics"), futures):
            try:
                results.append(future.result())
            except Exception:
                # Do not expose configured endpoint credentials or backend errors to the browser.
                results.append(None)
                errors.append(label + "_unavailable")
    payload = build_status(*results, time.time(), errors)
    if __package__:
        from .traces import trace_status
    else:
        from traces import trace_status
    payload["capabilities"]["traces"] = trace_status()
    return payload


def get_status() -> dict:
    global _cache, _expires
    with _cache_lock:
        if _cache is None or time.monotonic() >= _expires:
            _cache = collect_status()
            _expires = time.monotonic() + 5
        return _cache
