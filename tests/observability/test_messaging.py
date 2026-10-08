import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from seckill_observability import messaging as m
from performance.web import traces

ROOT = Path(__file__).resolve().parents[2]


class MessagingTests(unittest.TestCase):
    def test_durable_restart_retry_and_duplicate_state_commit(self):
        for service in ("order", "inventory"):
            with self.subTest(service=service), tempfile.TemporaryDirectory() as directory:
                for phase in ("create", "exercise"):
                    result = subprocess.run([sys.executable, str(Path(__file__).with_name("p2_repository_harness.py")),
                                             service, phase, str(Path(directory) / "outbox.sqlite")], cwd=ROOT,
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    if phase == "create":
                        self.assertIn("traceparent", json.loads(result.stdout))
                    else:
                        self.assertIn("durable restart", result.stdout)

    def test_delayed_roots_links_and_legacy_context_cleanup(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("p2_messaging_harness.py"))],
                                cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_untrusted_headers_legacy_stability_and_allowlist(self):
        parent = "00-" + "a" * 32 + "-" + "b" * 16 + "-03"
        message = SimpleNamespace(topic="orders", partition=0, offset=1, headers=[
            ("traceparent", parent.encode()), ("baggage", b"password=secret"), ("tracestate", b"invalid"),
            ("x-request-id", b"valid-id"), ("x-seckill-event-id", b"invalid"), ("unexpected", b"secret"), ("bad",)])
        metadata = m.message_metadata(message)
        self.assertEqual(metadata["traceparent"], parent)
        self.assertNotIn("tracestate", metadata)
        self.assertNotIn("baggage", metadata)
        self.assertEqual(metadata["event_id"], m.message_metadata(message)["event_id"])
        message.headers.append(("traceparent", parent.encode()))
        self.assertNotIn("traceparent", m.message_metadata(message))
        self.assertEqual(m.sanitize_metadata("x" * 2049), {})
        self.assertEqual(m.sanitize_metadata({"traceparent": "00-" + "0" * 32 + "-" + "0" * 16 + "-01"}), {"schema_version": 1})

    def test_async_query_filters_are_bounded(self):
        with patch.object(traces, "read_tempo", return_value={}) as reader:
            traces.search_traces({"service": ["order-worker"], "order_id": ["123"],
                                  "event_id": ["11111111-1111-4111-8111-111111111111"]})
            self.assertIn("span.seckill.order_id", reader.call_args.args[0])
        for invalid in ('1" || true', "-1", "9223372036854775808"):
            with self.assertRaises(ValueError):
                traces.search_traces({"order_id": [invalid]})
        with self.assertRaises(ValueError):
            traces.search_traces({"event_id": ['" || true']})

    def test_delayed_message_and_commit_failure_are_explicit(self):
        self.assertTrue(m._message_delayed(SimpleNamespace(timestamp=1)))
        self.assertFalse(m._message_delayed(SimpleNamespace()))
        consumer = SimpleNamespace(commit=lambda: (_ for _ in ()).throw(RuntimeError("commit failed")))
        previous = m.COMMIT_FAILURES.labels("inventory-result-consumer")._value.get()
        with self.assertRaises(RuntimeError):
            m.commit_offset(consumer, "inventory-result-consumer")
        self.assertEqual(m.COMMIT_FAILURES.labels("inventory-result-consumer")._value.get(), previous + 1)


if __name__ == "__main__":
    unittest.main()
