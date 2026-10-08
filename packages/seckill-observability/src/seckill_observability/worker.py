from __future__ import annotations

import logging
import threading
import time

from prometheus_client import CollectorRegistry, Counter, Gauge, ProcessCollector, PlatformCollector, start_http_server

from .context import log_context


class WorkerMonitor:
    """Own registry for the worker process. Failure remains visible until restart."""

    def __init__(self, roles: tuple[str, ...], registry=None) -> None:
        self.roles = frozenset(roles)
        self.registry = registry if registry is not None else CollectorRegistry()
        from .messaging import PUBLISHES, PROCESSES, TRANSITIONS, COMMIT_FAILURES, PROCESS_DURATION
        from .tracing import EXPORT_BATCHES
        for collector in (PUBLISHES, PROCESSES, TRANSITIONS, COMMIT_FAILURES, PROCESS_DURATION, EXPORT_BATCHES):
            self.registry.register(collector)
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        self.alive = Gauge("worker_task_alive", "Whether the task thread is running", ["role"], registry=self.registry)
        self.heartbeat = Gauge("worker_loop_last_poll_timestamp_seconds", "Last successful poll or publish attempt completion (including idle polls)", ["role"], registry=self.registry)
        self.progress = Gauge("worker_loop_last_progress_timestamp_seconds", "Last successful business work completion", ["role"], registry=self.registry)
        self.failures = Counter("worker_task_failures_total", "Unhandled task failures", ["role"], registry=self.registry)
        self.ready = Gauge("worker_ready", "Whether all expected task threads are alive", registry=self.registry)
        self._states = {role: False for role in roles}
        self._lock = threading.Lock()
        for role in roles:
            self.alive.labels(role).set(0)
            self.heartbeat.labels(role).set(0)
            self.progress.labels(role).set(0)
            self.failures.labels(role)
        self.ready.set(0)

    def start_server(self, port: int = 9106, addr: str = "0.0.0.0"):
        return start_http_server(port, addr=addr, registry=self.registry)

    def _check_role(self, role: str) -> None:
        if role not in self.roles:
            raise ValueError("Unknown worker role")

    def touch(self, role: str, progressed: bool = False) -> None:
        self._check_role(role)
        self.heartbeat.labels(role).set(time.time())
        if progressed:
            self.progress.labels(role).set(time.time())

    def _set_alive(self, role: str, value: bool) -> None:
        with self._lock:
            self._states[role] = value
            self.alive.labels(role).set(int(value))
            self.ready.set(int(all(self._states.values())))

    def run_task(self, role: str, target) -> None:
        self._check_role(role)
        logger = logging.getLogger("seckill.worker")
        with log_context(role=role):
            self._set_alive(role, True)
            try:
                target()
                # All current tasks are permanent loops; a normal return is unexpected too.
                self.failures.labels(role).inc()
                logger.error("worker task returned unexpectedly", extra={"event": "worker.task_exited"})
            except Exception:
                self.failures.labels(role).inc()
                logger.exception("worker task failed", extra={"event": "worker.task_exited"})
            finally:
                self._set_alive(role, False)

    def thread(self, role: str, target) -> threading.Thread:
        self._check_role(role)
        return threading.Thread(target=self.run_task, args=(role, target), name=role, daemon=True)
