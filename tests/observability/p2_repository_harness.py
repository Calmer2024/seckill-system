"""Real repositories + durable SQLite outbox across independent OS processes."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import BigInteger, create_engine, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from seckill_observability.context import current_context, log_context
from seckill_observability.messaging import TRANSITIONS, sanitize_metadata
from seckill_observability.tracing import SafeExporter

service, phase, database = sys.argv[1:4]
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / f"{service}_service"))
if service == "order":
    from app.application.services import order_service as module
    from app.models.order import OrderOutboxEvent as Outbox, Order
    from app.application.dto.order_dto import OrderCreatedEvent, InventoryResultEvent
    Repository, Publisher = module.OrderRepository, module.OrderOutboxPublisher
else:
    from app.services import inventory_service as module
    from app.models.inventory import InventoryOutboxEvent as Outbox, InventoryItem, InventoryReservation
    from app.schemas.inventory import InventoryResultEvent
    Repository, Publisher = module.InventoryRepository, module.InventoryOutboxPublisher
    module.settings.ENABLE_INVENTORY_OUTBOX = True


@compiles(BigInteger, "sqlite")
def compile_bigint(type_, compiler, **kw):
    return "INTEGER"


engine = create_engine("sqlite:///" + database)
Outbox.metadata.create_all(engine)
factory = sessionmaker(bind=engine, expire_on_commit=False)
exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(SafeExporter(exporter)))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("p2-test")

if phase == "create":
    with tracer.start_as_current_span("order.submit"), log_context(request_id="p2-durable-request"):
        with factory() as session:
            if service == "order":
                Repository(session).create_pending_order_and_outbox(OrderCreatedEvent(
                    order_id=123, user_id=4, product_id=5, quantity=1, unit_price="10.00", total_amount="10.00"))
            else:
                session.add(InventoryItem(product_id=5, product_name="fixture", unit_price=10, available_stock=9, reserved_stock=1, sold_stock=0))
                session.add(InventoryReservation(order_id=123, user_id=4, product_id=5, quantity=1, status="RESERVED"))
                session.commit()
                payload = InventoryResultEvent(order_id=123, user_id=4, product_id=5, quantity=1, status="RESERVED")
                with log_context(event_id="11111111-1111-4111-8111-111111111111"):
                    Repository(session).confirm_reservation_and_enqueue_result(payload)
                    Repository(session).confirm_reservation_and_enqueue_result(payload)
                assert session.query(Outbox).count() == 1
                assert TRANSITIONS.labels("inventory", "CONFIRMED")._value.get() == 1
            metadata = sanitize_metadata(session.execute(select(Outbox)).scalar_one().observability_metadata)
            assert metadata["request_id"] == "p2-durable-request"
            if service == "inventory":
                assert metadata["causation_id"] == "11111111-1111-4111-8111-111111111111"
    print(json.dumps(metadata))
else:
    class EndLoop(Exception):
        pass

    class Kafka:
        def __init__(self, fail):
            self.fail = fail
            self.headers = []

        def send(self, topic, payload, **kwargs):
            self.headers.append(dict(kwargs["headers"]))
            assert "traceparent" in self.headers[-1]
            assert kwargs["key"] == b"123"
            assert "traceparent" not in payload and "event_id" not in payload
            return self

        def get(self, timeout):
            assert timeout == 20
            if self.fail:
                raise RuntimeError("ack unavailable")
            return SimpleNamespace(partition=0)

    with factory() as session:
        original = sanitize_metadata(session.execute(select(Outbox)).scalar_one().observability_metadata)
    headers = []
    for fail in (True, False):
        publisher = Publisher.__new__(Publisher)
        publisher.monitor = None
        publisher.role = f"{service}-outbox-publisher"
        publisher.order_session_factory = factory
        publisher.inventory_session_factory = factory
        publisher.producer = module.KafkaEventProducer.__new__(module.KafkaEventProducer)
        kafka = Kafka(fail)
        publisher.producer._producer = kafka
        with patch.object(module.time, "sleep", side_effect=EndLoop()):
            try:
                publisher.run()
            except EndLoop:
                pass
        assert current_context() == {}
        headers.extend(kafka.headers)
        with factory() as session:
            event = session.execute(select(Outbox)).scalar_one()
            metadata = sanitize_metadata(event.observability_metadata)
            assert metadata["traceparent"] == original["traceparent"]
            assert metadata["event_id"] == original["event_id"]
            assert event.status == ("RETRY" if fail else "PUBLISHED")
            if fail:
                assert event.retry_count == 1
                event.next_retry_at = None
                session.commit()
    assert len(headers) == 2 and headers[0]["traceparent"] != headers[1]["traceparent"]
    assert headers[0]["x-seckill-event-id"] == headers[1]["x-seckill-event-id"]
    spans = exporter.get_finished_spans()
    attempts = [span for span in spans if span.name == "outbox.publish"]
    assert len(attempts) == 2 and attempts[0].status.status_code.name == "ERROR"
    assert all(format(span.context.trace_id, "032x") == original["traceparent"].split("-")[1] for span in attempts)
    assert len(attempts[1].links) == 1
    if service == "order":
        with factory() as session:
            payload = InventoryResultEvent(order_id=123, user_id=4, product_id=5, quantity=1, status="CONFIRMED")
            Repository(session).mark_inventory_confirmed(payload)
            Repository(session).mark_inventory_confirmed(payload)
            assert session.get(Order, 123).status == "CREATED"
            assert TRANSITIONS.labels("order", "CREATED")._value.get() == 1
            with tracer.start_as_current_span("payment.request") as payment_span:
                order = session.get(Order, 123)
                Repository(session).request_payment(order, module.Decimal("10.00"))
                Repository(session).request_payment(order, module.Decimal("10.00"))
                payment_event = session.execute(select(Outbox).where(Outbox.event_type=="PAYMENT_REQUESTED")).scalar_one()
                payment_meta = sanitize_metadata(payment_event.observability_metadata)
                assert payment_meta["event_id"] != original["event_id"]
                assert payment_meta["traceparent"].split("-")[1] != original["traceparent"].split("-")[1]
            assert TRANSITIONS.labels("order", "PAYING")._value.get() == 1
            result = module.PaymentRequestedEvent(order_id=123, user_id=4, amount="10.00")
            Repository(session).mark_payment_success(result)
            Repository(session).mark_payment_success(result)
            assert TRANSITIONS.labels("order", "PAID")._value.get() == 1
            previous = TRANSITIONS.labels("order", "PENDING_INVENTORY")._value.get()
            new_event = module.OrderCreatedEvent(order_id=124,user_id=5,product_id=6,quantity=1,unit_price="10.00",total_amount="10.00")
            with patch.object(session, "commit", side_effect=RuntimeError("commit rejected")):
                try:
                    Repository(session).create_pending_order_and_outbox(new_event)
                    raise AssertionError("commit should fail")
                except RuntimeError:
                    session.rollback()
            assert TRANSITIONS.labels("order", "PENDING_INVENTORY")._value.get() == previous
    print("durable restart, retry identity, parent/link, duplicate transition OK")

provider.shutdown()
