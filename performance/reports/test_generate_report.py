from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


GENERATOR = Path(__file__).with_name("generate_report.py")


class GenerateReportTest(unittest.TestCase):
    def test_k6_summary_export_values_reach_report(self) -> None:
        # k6 0.54 --summary-export writes metric fields directly, without "values".
        summary = {
            "metrics": {
                "http_reqs": {"count": 41249, "rate": 275.0004526898862},
                "http_req_duration": {"med": 1.909431, "p(95)": 2.6559816},
                "http_req_failed": {"value": 0, "fails": 41249, "passes": 0},
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary_path = root / "k6-summary.json"
            validation_path = root / "validation.json"
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            validation_path.write_text('{"passed": true, "checks": []}', encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    "--k6-summary",
                    str(summary_path),
                    "--validation",
                    str(validation_path),
                    "--output-dir",
                    str(root),
                    "--run-id",
                    "captured-k6-format",
                    "--scenario",
                    "product-read",
                    "--mode",
                    "baseline",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads((root / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["load"]["completed_requests"], 41249)
            self.assertAlmostEqual(report["load"]["actual_rps"], 275.0004526898862)
            self.assertAlmostEqual(report["load"]["p50_latency_ms"], 1.909431)
            self.assertAlmostEqual(report["load"]["p95_latency_ms"], 2.6559816)
            self.assertEqual(report["load"]["http_error_rate"], 0)
            self.assertIsNone(report["load"]["p99_latency_ms"])


if __name__ == "__main__":
    unittest.main()
