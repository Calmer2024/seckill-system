import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from performance.web import signals

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


class SignalsTests(unittest.TestCase):
    def test_explicit_investigation_ranges_reach_both_backends(self):
        end=int(time.time())-3600
        start=end-127
        payload={"status":"success","data":{"result":[]}}
        with patch.object(signals,'read',return_value=payload) as read:
            signals.search_logs({'start':[str(start)],'end':[str(end)],'service':['order-api']})
        query=parse_qs(urlparse(read.call_args.args[1]).query)
        self.assertEqual(query['start'],[str(start*10**9)])
        self.assertEqual(query['end'],[str(end*10**9)])
        with patch.object(signals,'read',return_value=payload) as read:
            signals.chart('http_rate',end,60,start)
        query=parse_qs(urlparse(read.call_args.args[1]).query)
        self.assertEqual(query['start'],[str(start)])
        self.assertEqual(query['end'],[str(end)])

    def test_investigation_ranges_reject_partial_future_and_excessive_dates(self):
        now=int(time.time())
        for params in ({'start':[str(now-60)]},{'start':['1'],'end':[str(now)]},{'start':[str(now)],'end':[str(now+120)]},{'start':[str(now)],'end':[str(now)]}):
            with self.subTest(params=params),self.assertRaises(ValueError):
                signals.explicit_range(params,now)

    def test_dashboard_time_presets_keep_query_point_budget(self):
        for window in ['60', '180', '360', '720', '1440', '2880', '10080', '20160', '43200']:
            self.assertEqual(signals.filters({'window': [window]}, {'window'}), int(window))
        payload = {'status': 'success', 'data': {'result': [{'metric': {}, 'values': [[n, '1'] for n in range(200)]}]}}
        with patch.object(signals, 'read', return_value=payload) as read:
            chart = signals.chart('http_rate', 1800000000, 43200)
        query = parse_qs(urlparse(read.call_args.args[1]).query)
        self.assertEqual(query['step'], ['21600'])
        self.assertEqual(len(chart['series'][0]['points']), 121)

    def test_rejects_query_url_duplicate_and_unsafe_ids(self):
        for params in ({"query": ["{}"]}, {"url": ["http://example.org"]}, {"service": ["mysql"]}, {"trace_id": ['" | drop']}, {"window": ["999"]}, {"window": ["5", "60"]}, {"order_id": ["9999999999999999999"]}, {"at": [str(int(time.time()))]}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                signals.search_logs(params)

    def test_literal_query_escape_and_private_fields(self):
        text = '" | json | service="foreign'
        payload = {"status": "success", "data": {"result": [{"stream": {"service": "order_worker", "instance": "worker"}, "values": [["1791000000000000000", json.dumps({"message": "token=abc Bearer xyz someone@example.com", "trace_id": "a"*32, "password": "secret", "user_id": "private"})]]}]}}
        with patch.object(signals, "read", return_value=payload) as read:
            result = signals.search_logs({"text": [text]})
        query = parse_qs(urlparse(read.call_args.args[1]).query)["query"][0]
        self.assertTrue(query.endswith(" |= " + json.dumps(text)))
        self.assertIn('namespace="seckill",environment="local"', query)
        self.assertEqual(result["logs"][0]["fields"]["trace_id"], "a"*32)
        self.assertNotIn("password", result["logs"][0]["fields"])
        self.assertNotIn("user_id", result["logs"][0]["fields"])
        self.assertNotIn("abc", result["logs"][0]["fields"]["message"])

    def test_anchor_cannot_search_outside_retention(self):
        with self.assertRaises(ValueError):
            signals.search_logs({"trace_id": ["a"*32], "at": [str(int(time.time()) - 73*3600)]})

    def test_business_evidence_stale_does_not_show_cached_zero(self):
        with patch.object(signals, "chart", side_effect=lambda key,*_: {"id":key,"status":"ok","series":[{"points":[[1,0]]}]}), patch.object(signals, "read", return_value={"status":"success","data":{"result":[]}}):
            result = signals.metrics({})
        for chart in result["charts"]:
            if chart["id"] in {"outbox_pending", "negative_stock"}:
                self.assertEqual(chart["status"], "stale")
                self.assertEqual(chart["series"], [])

    def test_alert_outage_is_not_no_alerts(self):
        with patch.object(signals, "read", side_effect=signals.SignalUnavailable):
            result = signals.alerts({})
        self.assertEqual(result["alert_status"], "unavailable")
        self.assertEqual(result["notification_status"], "unavailable")

    def test_legacy_metric_services_are_queried_and_normalized(self):
        payload = {"status":"success","data":{"result":[{"metric":{"service":"order"},"values":[[100,"2"]]},{"metric":{"service":"inventory"},"values":[[100,"NaN"]]}]}}
        with patch.object(signals, "read", return_value=payload) as read:
            result = signals.chart("http_rate",100,15)
        query = parse_qs(urlparse(read.call_args.args[1]).query)["query"][0]
        self.assertIn('service=~"user|product|order|inventory"',query)
        self.assertEqual(result["series"][0]["labels"]["service"], "order-api")
        self.assertEqual(result["series"][1]["labels"]["service"], "inventory-api")
        self.assertIsNone(result["series"][1]["points"][0][1])


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.receiver = module("receiver_test", "performance/monitoring/runtime/receiver.py")
        self.receiver.DB = str(Path(self.temporary.name) / "events.sqlite")
        self.alert = {"status":"firing", "labels":{"alertname":"Example","environment":"local","service":"order-api","secret":"ignored"}, "annotations":{"summary":"Example"}, "fingerprint":"1234", "startsAt":"2026-10-03T00:00:00Z", "endsAt":"2026-10-03T00:01:00Z"}

    def tearDown(self):
        self.temporary.cleanup()

    def test_durable_ack_and_idempotent_firing_resolution(self):
        self.receiver.accept({"version":"4","alerts":[self.alert]})
        self.alert["endsAt"] = "2026-10-03T00:02:00Z"
        self.receiver.accept({"version":"4","alerts":[self.alert]})
        self.assertEqual(len(self.receiver.events()), 1)
        self.alert["status"] = "resolved"
        self.receiver.accept({"version":"4","alerts":[self.alert]})
        reloaded = module("receiver_reloaded", "performance/monitoring/runtime/receiver.py")
        reloaded.DB = self.receiver.DB
        self.assertEqual([r["status"] for r in reloaded.events()], ["resolved", "firing"])
        self.assertNotIn("secret", reloaded.events()[0]["labels"])

    def test_rejects_foreign_scope_and_atomic_batch(self):
        foreign = {**self.alert,"labels":{"alertname":"Foreign","environment":"production"}}
        with self.assertRaises(ValueError):
            self.receiver.accept({"version":"4","alerts":[self.alert, foreign]})
        self.assertEqual(self.receiver.events(), [])

    def test_storage_failure_is_not_acknowledged(self):
        self.receiver.DB = str(Path(self.temporary.name) / "missing" / "db")
        import sqlite3
        with self.assertRaises(sqlite3.Error):
            self.receiver.accept({"version":"4","alerts":[self.alert]})


if __name__ == "__main__":
    unittest.main()
