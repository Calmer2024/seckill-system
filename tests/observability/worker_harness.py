"""Exercise the actual consumer loops and HTTP client with no database or Kafka traffic."""
from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from seckill_observability.context import current_context, log_context
from seckill_observability.logging import ContextFilter, JsonFormatter
from seckill_observability.worker import WorkerMonitor

service = sys.argv[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / f"{service}_service"))
if service == "order":
    import httpx
    from app.application.services import order_service as module
    classes = (module.InventoryResultConsumer, module.PaymentResultConsumer)
else:
    from app.services import inventory_service as module
    classes = (module.OrderCreatedConsumer,)


class EndOfHarness(Exception):
    pass


for consumer_class in classes:
    for failure in ("none", "business", "offset"):
        fail = failure != "none"
        monitor = WorkerMonitor(("test-consumer",))
        instance = consumer_class.__new__(consumer_class)
        instance.role = "test-consumer"
        instance.monitor = monitor
        message = SimpleNamespace(value={"order_id": 123, "user_id": 100, "product_id": 4, "quantity": 1,
                                         "status": "CONFIRMED", "amount": "10.00"}, topic="test", partition=0, offset=5)
        instance.consumer = MagicMock()
        instance.consumer.config = {"group_id": "test-group"}
        instance.consumer.poll.side_effect = [{0: [message]}, EndOfHarness()]
        session = MagicMock()
        instance.order_session_factory = lambda: session
        instance.inventory_session_factory = lambda: session
        instance.stock_cache = MagicMock()
        instance.direct_producer = MagicMock()
        repository = MagicMock()
        repository.confirm_reservation_and_enqueue_result.return_value = SimpleNamespace(status="CONFIRMED", user_id=100, product_id=4, order_id=123)
        if failure == "offset":
            instance.consumer.commit.side_effect = RuntimeError("offset commit failed")
        if failure == "business":
            repository.mark_inventory_confirmed.side_effect = RuntimeError("commit failed")
            repository.mark_payment_success.side_effect = RuntimeError("commit failed")
            repository.confirm_reservation_and_enqueue_result.side_effect = RuntimeError("commit failed")
        repository_name = "OrderRepository" if service == "order" else "InventoryRepository"
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.addFilter(ContextFilter())
        handler.setFormatter(JsonFormatter(service + "-worker"))
        module.logger.handlers = [handler]
        module.logger.propagate = False
        module.logger.setLevel(logging.INFO)
        with patch.object(module, repository_name, return_value=repository):
            try:
                instance.run()
            except (EndOfHarness, RuntimeError):
                pass
        assert instance.consumer.commit.call_count == (0 if failure == "business" else 1)
        assert session.close.call_count == 1
        assert instance.consumer.poll.call_args_list[0].kwargs == {"timeout_ms": 1000, "max_records": 1}
        assert monitor.heartbeat.labels("test-consumer")._value.get() > 0
        assert bool(monitor.progress.labels("test-consumer")._value.get()) == (not fail)
        assert current_context() == {}
        if fail:
            records = [json.loads(line) for line in output.getvalue().splitlines()]
            record = next(record for record in records if record.get("event") == "consumer.process_failed")
            assert record["order_id"] == 123 and record["offset"] == 5 and record["group"] == "test-group"

if service == "order":
    client = module.InventoryServiceClient()
    client.client.close()
    requests = []
    client.client = httpx.Client(base_url="http://inventory", transport=httpx.MockTransport(
        lambda request: requests.append(request) or httpx.Response(200, json={"status": "RESERVED"})))
    with log_context(request_id="upstream-request"):
        client.reserve(1, 2, 3, 1)
        client.cancel(1)
    assert all(request.headers["X-Request-ID"] == "upstream-request" for request in requests)
    assert current_context() == {}
    client.client.close()

print(service + " consumer contracts OK")
