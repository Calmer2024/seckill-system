"""Opt-in real Kafka/Collector smoke, isolated topics and SQLite business fixtures.

Run each phase in a fresh container with P2_FIXTURE_DIR and P2_TOPIC_PREFIX.
Never accesses the application's MySQL business databases or existing Kafka groups.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import BigInteger, create_engine, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from opentelemetry import trace
from seckill_observability.context import log_context
from seckill_observability.logging import configure_logging
from seckill_observability.messaging import sanitize_metadata
from seckill_observability.tracing import configure_tracing

service, phase = sys.argv[1:3]
prefix = os.environ["P2_TOPIC_PREFIX"]
directory = Path(os.environ["P2_FIXTURE_DIR"])
directory.mkdir(exist_ok=True)
if service == "order":
    from app.application.services import order_service as module
    from app.models.order import OrderOutboxEvent as Outbox, Order
    from app.application.dto.order_dto import OrderCreatedEvent
    Repository, Publisher, Consumer = module.OrderRepository, module.OrderOutboxPublisher, module.InventoryResultConsumer
    module.settings.KAFKA_PAYMENT_TOPIC = prefix + "-payments"
    module.settings.KAFKA_INVENTORY_RESULT_GROUP_ID = prefix + "-order-group"
else:
    from app.services import inventory_service as module
    from app.models.inventory import InventoryOutboxEvent as Outbox, InventoryItem, InventoryReservation
    Repository, Publisher, Consumer = module.InventoryRepository, module.InventoryOutboxPublisher, module.OrderCreatedConsumer
    module.settings.KAFKA_ORDER_CREATED_GROUP_ID = prefix + "-inventory-group"
    module.settings.ENABLE_INVENTORY_OUTBOX = True
    module.settings.ENABLE_REDIS_STOCK_RESERVATION = False
module.settings.KAFKA_ORDER_CREATED_TOPIC = prefix + "-orders"
module.settings.KAFKA_INVENTORY_RESULT_TOPIC = prefix + "-inventory"


@compiles(BigInteger, "sqlite")
def bigint(type_, compiler, **kw):
    return "INTEGER"


engine = create_engine("sqlite:///" + str(directory / (service + ".sqlite")))
Outbox.metadata.create_all(engine)
factory = sessionmaker(bind=engine, expire_on_commit=False)
configure_logging("INFO", "order-api" if phase == "create" else service + "-worker")
provider = configure_tracing(None, "order-api" if phase == "create" else service + "-worker", (engine,))


class EndLoop(Exception):
    pass


try:
    if phase == "create":
        module.ensure_topics_exist()
        with trace.get_tracer("p2-validation").start_as_current_span("order.submit"), log_context(request_id=prefix, order_id=999800001):
            with factory() as session:
                Repository(session).create_pending_order_and_outbox(OrderCreatedEvent(order_id=999800001,
                    user_id=999800002, product_id=999800003, quantity=1, unit_price="10.00", total_amount="10.00"))
                metadata = sanitize_metadata(session.execute(select(Outbox)).scalar_one().observability_metadata)
                print("P2_TRACE=" + metadata["traceparent"].split("-")[1], flush=True)
    elif phase == "publish":
        publisher = Publisher(factory)
        try:
            with patch.object(module.time, "sleep", side_effect=EndLoop()):
                try:
                    publisher.run()
                except EndLoop:
                    pass
        finally:
            publisher.producer._producer.close(timeout=5)
        with factory() as session:
            event = session.execute(select(Outbox)).scalar_one()
            assert event.status == "PUBLISHED", event.status
            print("P2_EVENT=" + sanitize_metadata(event.observability_metadata)["event_id"], flush=True)
    elif phase == "consume":
        if service == "inventory":
            with factory() as session:
                session.add(InventoryItem(product_id=999800003, product_name="p2 isolated", unit_price=10, available_stock=9, reserved_stock=1, sold_stock=0))
                session.add(InventoryReservation(order_id=999800001, user_id=999800002, product_id=999800003, quantity=1, status="RESERVED"))
                session.commit()
            from unittest.mock import MagicMock
            consumer = Consumer(factory, MagicMock())
        else:
            consumer = Consumer(factory)
        poll, commit = consumer.consumer.poll, consumer.consumer.commit
        committed = False
        empty_polls = 0

        def one_message(**kwargs):
            global empty_polls
            if committed:
                raise EndLoop()
            batches = poll(**kwargs)
            empty_polls += int(not batches)
            if empty_polls > 30:
                raise TimeoutError("isolated Kafka message was not received")
            return batches

        def acknowledged():
            global committed
            commit()
            committed = True

        consumer.consumer.poll = one_message
        consumer.consumer.commit = acknowledged
        try:
            try:
                consumer.run()
            except EndLoop:
                pass
        finally:
            consumer.consumer.close()
            if service == "inventory":
                consumer.direct_producer._producer.close(timeout=5)
        with factory() as session:
            if service == "inventory":
                assert session.get(InventoryReservation, 999800001).status == "CONFIRMED"
                metadata = sanitize_metadata(session.execute(select(Outbox)).scalar_one().observability_metadata)
                assert metadata.get("causation_id")
            else:
                assert session.get(Order, 999800001).status == "CREATED"
                print("P2_FINAL_STATUS=CREATED", flush=True)
    else:
        raise ValueError("unknown phase")
finally:
    if provider:
        provider.force_flush(timeout_millis=5000)
        provider.shutdown()
