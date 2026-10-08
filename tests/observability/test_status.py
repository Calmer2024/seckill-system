from __future__ import annotations

import json
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import urlopen

from performance.web import observability, server


class StatusTests(unittest.TestCase):
    def target(self, age=0, health="up"):
        return {"labels": {"job": "order_worker", "instance": "order_worker:9106"}, "health": health,
                "lastScrape": datetime.fromtimestamp(1000 - age, timezone.utc).isoformat()}

    def metrics(self, alive="1", poll="999", progress="0", failures="0"):
        return {"result": [{"metric": {"__name__": name, "job": "order_worker", "instance": "order_worker:9106", "role": "order-outbox-publisher"}, "value": [1000, value]}
                           for name, value in (("worker_task_alive", alive), ("worker_loop_last_poll_timestamp_seconds", poll),
                                               ("worker_loop_last_progress_timestamp_seconds", progress), ("worker_task_failures_total", failures))]}

    def test_missing_is_not_healthy_or_zero(self):
        status = observability.build_status({"activeTargets": []}, {"result": []}, 1000, [])
        self.assertTrue(all(row["status"] == "not_configured" for row in status["services"]))
        status = observability.build_status({"activeTargets": [self.target()]}, {"result": []}, 1000, [])
        row = next(row for row in status["services"] if row["service"] == "order-worker")
        self.assertEqual(row["status"], "not_instrumented")
        self.assertIsNone(row["tasks"][0]["alive"])

    def test_failed_thread_and_idle_poll_are_distinct(self):
        status = observability.build_status({"activeTargets": [self.target()]}, self.metrics(), 1000, [])
        task = next(row for row in status["services"] if row["service"] == "order-worker")["tasks"][0]
        self.assertEqual(task["status"], "up")
        self.assertIsNone(task["progress_age_seconds"])
        status = observability.build_status({"activeTargets": [self.target()]}, self.metrics(alive="0", failures="1"), 1000, [])
        row = next(row for row in status["services"] if row["service"] == "order-worker")
        self.assertEqual(row["status"], "degraded")
        self.assertEqual(row["tasks"][0]["failures"], 1)

    def test_stale_and_down_targets_do_not_show_cached_alive(self):
        for target in (self.target(age=31), self.target(health="down")):
            status = observability.build_status({"activeTargets": [target]}, self.metrics(), 1000, [])
            row = next(row for row in status["services"] if row["service"] == "order-worker")
            self.assertIsNone(row["tasks"][0]["alive"])
            self.assertEqual(row["tasks"][0]["status"], "unavailable")

    def test_collector_error_and_nonfinite_are_explicit(self):
        status = observability.build_status(None, None, 1000, ["targets_unavailable"])
        self.assertEqual(status["status"], "unavailable")
        self.assertEqual(status["scope"], "environment_live")
        self.assertNotIn("run_id", status)
        self.assertIsNone(observability.finite_number("NaN"))
        with patch.object(observability, "read_prometheus", side_effect=TimeoutError):
            self.assertEqual(observability.collect_status()["status"], "unavailable")

    def test_status_cache_limits_backend_queries(self):
        with patch.object(observability, "_cache", None), patch.object(observability, "_expires", 0), patch.object(observability, "collect_status", return_value={"status": "ok"}) as collect:
            observability.get_status()
            observability.get_status()
            self.assertEqual(collect.call_count, 1)

    def test_endpoint_is_read_only_and_asset_available(self):
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.PerformanceHandler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(server, "observability_status", return_value={"scope": "environment_live"}):
                with urlopen(f"http://127.0.0.1:{http.server_port}/api/performance/observability/status") as response:
                    self.assertEqual(json.load(response)["scope"], "environment_live")
            with urlopen(f"http://127.0.0.1:{http.server_port}/observability.js") as response:
                self.assertEqual(response.status, 200)
        finally:
            http.shutdown()
            http.server_close()
            thread.join(2)


if __name__ == "__main__":
    unittest.main()
