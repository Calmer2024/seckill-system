from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class IntegrationTests(unittest.TestCase):
    def test_actual_consumer_loops_and_http_client(self):
        for service in ("order", "inventory"):
            with self.subTest(service=service):
                result = subprocess.run([sys.executable, str(Path(__file__).with_name("worker_harness.py")), service],
                                        cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("contracts OK", result.stdout)

    def test_product_four_process_metrics_aggregate(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": directory,
                   "PYTHONPATH": str(ROOT / "product_service")}
            code = 'from app.observability.metrics import record_http_request; record_http_request("GET", "/api/products/{product_id}", 200, 0.1)'
            processes = [subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            for process in processes:
                output, error = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, output + error)
            payload = subprocess.check_output([sys.executable, "-c", 'from app.observability.metrics import metrics_payload; print(metrics_payload().decode())'], env=env, text=True, timeout=10)
            line = next(line for line in payload.splitlines() if line.startswith('http_requests_total{'))
            self.assertTrue(line.endswith(' 4.0'), line)
            self.assertIn('path="/api/products/{product_id}"', line)


if __name__ == "__main__":
    unittest.main()
