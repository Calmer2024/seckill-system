from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import generate_latest

from seckill_observability.context import current_context, log_context, outbound_request_headers, seckill_outcome, validate_request_id
from seckill_observability.http import RequestContextMiddleware
from seckill_observability.logging import ContextFilter, JsonFormatter, configure_logging, redact
from seckill_observability.worker import WorkerMonitor


class LogTests(unittest.TestCase):
    def test_quoted_json_and_dict_secrets_are_redacted(self):
        self.assertNotIn("hidden-value", redact('{"password": "hidden-value"}'))
        self.assertNotIn("hidden-value", redact("{'token': 'hidden-value'}"))

    def test_schema_redacts_sensitive_data_and_preserves_states(self):
        formatter = JsonFormatter("order-api")
        record = logging.LogRecord("business", logging.INFO, "test", 1,
                                   "Bearer abc.def password=secret mysql+pymysql://root:private@db/x user@example.com 13812345678", (), None)
        record.order_status = "PAYING"
        record.payment_status = "PROCESSING"
        record.authorization = "private"
        record.user_id = 123
        record.keyword = "sensitive"
        with log_context(request_id="request-1"):
            ContextFilter().filter(record)
        payload = json.loads(formatter.format(record))
        self.assertEqual(payload["request_id"], "request-1")
        self.assertEqual(payload["order_status"], "PAYING")
        self.assertEqual(payload["payment_status"], "PROCESSING")
        for secret in ("abc.def", "secret", "private", "user@example.com", "13812345678"):
            self.assertNotIn(secret, payload["message"])
        for excluded in ("authorization", "user_id", "keyword"):
            self.assertNotIn(excluded, payload)

    def test_exception_stack_is_single_json_and_redacted(self):
        try:
            raise RuntimeError("password=secret\nBearer abc.def")
        except RuntimeError:
            import sys
            record = logging.LogRecord("worker", logging.ERROR, "test", 1, "failed", (), sys.exc_info())
        result = JsonFormatter("inventory-worker").format(record)
        self.assertEqual(len(result.splitlines()), 1)
        payload = json.loads(result)
        self.assertIn("RuntimeError", payload["exception"])
        self.assertNotIn("abc.def", payload["exception"])
        self.assertNotIn("secret", payload["exception"])

    def test_context_cleanup_and_request_header_validation(self):
        with log_context(request_id="req-1"):
            self.assertEqual(outbound_request_headers(), {"X-Request-ID": "req-1"})
            with log_context(order_id=10):
                self.assertEqual(current_context()["order_id"], 10)
            self.assertNotIn("order_id", current_context())
        self.assertEqual(current_context(), {})
        self.assertNotEqual(validate_request_id("bad\r\nheader"), "bad\r\nheader")
        self.assertEqual(len(validate_request_id("x" * 100)), 32)
        self.assertEqual(seckill_outcome("unbounded-value-1"), "other")

    def test_uvicorn_handlers_use_one_schema(self):
        root = logging.getLogger()
        handlers, level = root.handlers[:], root.level
        uvicorn = {name: (logging.getLogger(name).handlers[:], logging.getLogger(name).propagate, logging.getLogger(name).disabled)
                   for name in ("uvicorn", "uvicorn.error", "uvicorn.access")}
        httpx_level = logging.getLogger("httpx").level
        try:
            configure_logging(service="user")
            self.assertEqual(len(root.handlers), 1)
            self.assertTrue(logging.getLogger("uvicorn.error").propagate)
            self.assertEqual(logging.getLogger("uvicorn.error").handlers, [])
            self.assertTrue(logging.getLogger("uvicorn.access").disabled)
        finally:
            root.handlers, root.level = handlers, level
            for name, (saved_handlers, propagate, disabled) in uvicorn.items():
                logger = logging.getLogger(name)
                logger.handlers, logger.propagate, logger.disabled = saved_handlers, propagate, disabled
            logging.getLogger("httpx").setLevel(httpx_level)


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.records = []
        self.stream = io.StringIO()
        self.logger = logging.getLogger("test.request-context")
        self.logger.handlers.clear()
        self.logger.propagate = False
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(self.stream)
        handler.addFilter(ContextFilter())
        handler.setFormatter(JsonFormatter("test"))
        self.logger.addHandler(handler)
        self.app = FastAPI()

        @self.app.get("/items/{item_id}")
        async def item(item_id: int):
            await asyncio.sleep(0.001 * (item_id % 4))
            self.logger.info("business", extra={"event": "business", "order_id": item_id})
            return {"context": current_context()}

        @self.app.get("/sync")
        def sync():
            self.logger.info("sync business", extra={"event": "sync"})
            return outbound_request_headers()

        @self.app.get("/stream")
        async def stream():
            async def chunks():
                self.logger.info("streamed", extra={"event": "stream"})
                yield b"streamed"
            return StreamingResponse(chunks())

        @self.app.get("/failure")
        async def failure():
            raise RuntimeError("password=secret")

        @self.app.exception_handler(Exception)
        async def error(request, exc):
            return JSONResponse({"error": "failed"}, status_code=500, headers={"X-Request-ID": request.state.request_id})

        self.app.add_middleware(RequestContextMiddleware, record_http_request=lambda *args: self.records.append(args), logger=self.logger)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.logger.handlers.clear()

    async def test_concurrent_context_and_template_cardinality(self):
        responses = await asyncio.gather(*(self.client.get(f"/items/{i}", headers={"X-Request-ID": f"req-{i}"}) for i in range(30)))
        for index, response in enumerate(responses):
            self.assertEqual(response.json()["context"]["request_id"], f"req-{index}")
            self.assertEqual(response.headers["X-Request-ID"], f"req-{index}")
        for index in range(20):
            await self.client.get(f"/random/{index}?password=secret")
        self.assertEqual({entry[1] for entry in self.records}, {"/items/{item_id}", "__unmatched__"})
        logs = [json.loads(line) for line in self.stream.getvalue().splitlines()]
        for record in logs:
            if record.get("event") == "business":
                self.assertEqual(record["request_id"], f"req-{record['order_id']}")
        self.assertNotIn("secret", self.stream.getvalue())
        self.assertEqual(current_context(), {})

    async def test_sync_endpoint_stream_error_and_exclusions(self):
        sync = await self.client.get("/sync", headers={"X-Request-ID": "sync-request"})
        self.assertEqual(sync.json()["X-Request-ID"], "sync-request")
        stream = await self.client.get("/stream", headers={"X-Request-ID": "stream-request"})
        self.assertEqual(stream.text, "streamed")
        failure = await self.client.get("/failure", headers={"X-Request-ID": "failure-request"})
        self.assertEqual(failure.status_code, 500)
        self.assertEqual(failure.headers["X-Request-ID"], "failure-request")
        await self.client.get("/metrics")
        self.assertEqual(len(self.records), 3)
        self.assertEqual(current_context(), {})
        records = [json.loads(line) for line in self.stream.getvalue().splitlines()]
        self.assertEqual(next(record for record in records if record.get("event") == "stream")["request_id"], "stream-request")
        self.assertEqual(next(record for record in records if record.get("event") == "http_request_failed")["request_id"], "failure-request")


class WorkerTests(unittest.TestCase):
    def test_thread_failure_surfaces_while_other_thread_survives(self):
        monitor = WorkerMonitor(("publish", "consume"))
        ready = threading.Event()
        stop = threading.Event()

        def consume():
            monitor.touch("consume")  # Idle polling is healthy, not business progress.
            ready.set()
            stop.wait(2)

        def publish():
            raise RuntimeError("db unavailable")

        consumer = monitor.thread("consume", consume)
        publisher = monitor.thread("publish", publish)
        consumer.start()
        self.assertTrue(ready.wait(2))
        publisher.start()
        publisher.join(2)
        try:
            self.assertTrue(consumer.is_alive())
            self.assertEqual(monitor.alive.labels("publish")._value.get(), 0)
            self.assertEqual(monitor.failures.labels("publish")._value.get(), 1)
            self.assertEqual(monitor.alive.labels("consume")._value.get(), 1)
            self.assertGreater(monitor.heartbeat.labels("consume")._value.get(), 0)
            self.assertEqual(monitor.progress.labels("consume")._value.get(), 0)
            self.assertEqual(monitor.ready._value.get(), 0)
            self.assertNotIn(b"http_requests", generate_latest(monitor.registry))
        finally:
            stop.set()
            consumer.join(2)

    def test_live_metrics_endpoint_and_unknown_roles(self):
        monitor = WorkerMonitor(("publish",))
        server, thread = monitor.start_server(0, "127.0.0.1")
        try:
            response = httpx.get(f"http://127.0.0.1:{server.server_port}/metrics")
            self.assertEqual(response.status_code, 200)
            self.assertIn('worker_task_alive{role="publish"} 0.0', response.text)
            with self.assertRaises(ValueError):
                monitor.touch("free-text-label")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == "__main__":
    unittest.main()
