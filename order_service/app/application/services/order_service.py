import json
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.dto.order_dto import (
    InventoryResultEvent,
    OrderCreatedEvent,
    PaymentAcceptedResponse,
    PaymentRequest,
    PaymentRequestedEvent,
    SeckillOrderAcceptedResponse,
    SeckillOrderRequest,
)
from app.core.config import settings
from app.core.exceptions.business_exception import BusinessException
from app.core.security import CurrentUser
from app.infrastructure.logging.logger import get_logger
from app.models.order import Order, OrderOutboxEvent, PaymentRecord, UserPurchaseRecord
from app.models.product import Product


logger = get_logger(__name__)

ACTIVE_ORDER_STATUSES = {"PENDING_INVENTORY", "CREATED", "PAYING", "PAID"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SnowflakeIdGenerator:
    def __init__(self, datacenter_id: int, worker_id: int, epoch_milliseconds: int) -> None:
        self.datacenter_id = datacenter_id
        self.worker_id = worker_id
        self.epoch_milliseconds = epoch_milliseconds
        self.sequence = 0
        self.last_timestamp = -1
        self.sequence_mask = 4095
        self.lock = threading.Lock()

    def next_id(self) -> int:
        with self.lock:
            timestamp = int(time.time() * 1000)
            if timestamp < self.last_timestamp:
                timestamp = self.last_timestamp

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.sequence_mask
                if self.sequence == 0:
                    while timestamp <= self.last_timestamp:
                        timestamp = int(time.time() * 1000)
            else:
                self.sequence = 0

            self.last_timestamp = timestamp
            return (
                ((timestamp - self.epoch_milliseconds) << 22)
                | (self.datacenter_id << 17)
                | (self.worker_id << 12)
                | self.sequence
            )


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_product(self, product_id: int) -> Product | None:
        statement = select(Product).where(Product.id == product_id)
        return self.session.execute(statement).scalar_one_or_none()


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_order_id(self, order_id: int, user_id: int | None = None) -> Order | None:
        statement = select(Order).where(Order.order_id == order_id)
        if user_id is not None:
            statement = statement.where(Order.user_id == user_id)
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_user_id(self, user_id: int) -> list[Order]:
        statement = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        return list(self.session.execute(statement).scalars().all())

    def find_active_by_user_and_product(self, user_id: int, product_id: int) -> Order | None:
        statement = (
            select(Order)
            .where(
                Order.user_id == user_id,
                Order.product_id == product_id,
                Order.status.in_(ACTIVE_ORDER_STATUSES),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def create_pending_order_and_outbox(self, event: OrderCreatedEvent) -> None:
        order = Order(
            order_id=event.order_id,
            user_id=event.user_id,
            product_id=event.product_id,
            quantity=event.quantity,
            unit_price=event.unit_price,
            total_amount=event.total_amount,
            status="PENDING_INVENTORY",
        )
        outbox = OrderOutboxEvent(
            aggregate_id=event.order_id,
            user_id=event.user_id,
            topic=settings.KAFKA_ORDER_CREATED_TOPIC,
            event_type="ORDER_CREATED",
            payload=json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
            status="NEW",
        )
        self.session.add(order)
        self.session.add(outbox)
        self.session.commit()

    def request_payment(self, order: Order, amount: Decimal) -> tuple[str, str]:
        payment = self.session.get(PaymentRecord, order.order_id)
        if payment and payment.status == "SUCCESS":
            if order.status != "PAID":
                order.status = "PAID"
                order.failure_reason = None
                self.session.commit()
            return order.status, payment.status

        if payment and payment.status == "PROCESSING":
            if order.status != "PAYING":
                order.status = "PAYING"
                self.session.commit()
            return order.status, payment.status

        order.status = "PAYING"
        order.failure_reason = None
        if payment is None:
            payment = PaymentRecord(
                order_id=order.order_id,
                user_id=order.user_id,
                amount=amount,
                status="PROCESSING",
            )
            self.session.add(payment)
        else:
            payment.amount = amount
            payment.status = "PROCESSING"

        event = PaymentRequestedEvent(order_id=order.order_id, user_id=order.user_id, amount=amount)
        outbox = OrderOutboxEvent(
            aggregate_id=order.order_id,
            user_id=order.user_id,
            topic=settings.KAFKA_PAYMENT_TOPIC,
            event_type="PAYMENT_REQUESTED",
            payload=json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
            status="NEW",
        )
        self.session.add(outbox)
        self.session.commit()
        return order.status, payment.status

    def mark_inventory_confirmed(self, payload: InventoryResultEvent) -> None:
        order = self.get_by_order_id(payload.order_id)
        if order is None:
            self.session.rollback()
            return
        if order.status in {"CREATED", "PAYING", "PAID"}:
            self.session.rollback()
            return
        if order.status == "FAILED":
            self.session.rollback()
            return

        order.status = "CREATED"
        order.failure_reason = None

        purchase_record = self.session.execute(
            select(UserPurchaseRecord).where(
                UserPurchaseRecord.user_id == payload.user_id,
                UserPurchaseRecord.product_id == payload.product_id,
            )
        ).scalar_one_or_none()
        if purchase_record is None:
            self.session.add(
                UserPurchaseRecord(
                    user_id=payload.user_id,
                    product_id=payload.product_id,
                    order_id=payload.order_id,
                )
            )

        self.session.commit()

    def mark_inventory_failed(self, payload: InventoryResultEvent) -> None:
        order = self.get_by_order_id(payload.order_id)
        if order is None:
            self.session.rollback()
            return
        if order.status == "FAILED":
            self.session.rollback()
            return
        if order.status == "PAID":
            self.session.rollback()
            return

        order.status = "FAILED"
        order.failure_reason = payload.failure_reason or "INVENTORY_REJECTED"
        self.session.commit()

    def mark_payment_success(self, payload: PaymentRequestedEvent) -> None:
        order = self.get_by_order_id(payload.order_id)
        if order is None:
            self.session.rollback()
            return
        payment = self.session.get(PaymentRecord, payload.order_id)
        if payment is None:
            payment = PaymentRecord(
                order_id=payload.order_id,
                user_id=payload.user_id,
                amount=payload.amount,
                status="SUCCESS",
            )
            self.session.add(payment)
        else:
            payment.status = "SUCCESS"
            payment.amount = payload.amount

        if order.status != "PAID":
            order.status = "PAID"
            order.failure_reason = None

        self.session.commit()

    def list_pending_outbox_events(self, limit: int) -> list[OrderOutboxEvent]:
        now = utcnow()
        statement = (
            select(OrderOutboxEvent)
            .where(
                OrderOutboxEvent.status.in_(["NEW", "RETRY"]),
                or_(OrderOutboxEvent.next_retry_at.is_(None), OrderOutboxEvent.next_retry_at <= now),
            )
            .order_by(OrderOutboxEvent.id.asc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def mark_outbox_published(self, event: OrderOutboxEvent) -> None:
        result = self.session.execute(
            update(OrderOutboxEvent)
            .where(
                OrderOutboxEvent.id == event.id,
                OrderOutboxEvent.aggregate_id == event.aggregate_id,
                OrderOutboxEvent.user_id == event.user_id,
            )
            .values(
                status="PUBLISHED",
                published_at=utcnow(),
            )
        )
        if result.rowcount == 0:
            self.session.rollback()
            return
        self.session.commit()

    def mark_outbox_retry(self, event: OrderOutboxEvent) -> None:
        snapshot = self.session.execute(
            select(OrderOutboxEvent.retry_count).where(
                OrderOutboxEvent.id == event.id,
                OrderOutboxEvent.aggregate_id == event.aggregate_id,
                OrderOutboxEvent.user_id == event.user_id,
            )
        ).one_or_none()
        if snapshot is None:
            self.session.rollback()
            return
        retry_count = snapshot[0] + 1
        self.session.execute(
            update(OrderOutboxEvent)
            .where(
                OrderOutboxEvent.id == event.id,
                OrderOutboxEvent.aggregate_id == event.aggregate_id,
                OrderOutboxEvent.user_id == event.user_id,
            )
            .values(
                retry_count=retry_count,
                status="RETRY",
                next_retry_at=utcnow() + timedelta(seconds=min(retry_count * 2, 30)),
            )
        )
        self.session.commit()


class InventoryServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InventoryServiceClient:
    def __init__(self) -> None:
        self.client = httpx.Client(
            base_url=settings.INVENTORY_SERVICE_URL,
            timeout=settings.INVENTORY_SERVICE_TIMEOUT_SECONDS,
        )

    def reserve(self, order_id: int, user_id: int, product_id: int, quantity: int) -> None:
        self._post(
            "/internal/inventory/reservations",
            {
                "order_id": order_id,
                "user_id": user_id,
                "product_id": product_id,
                "quantity": quantity,
            },
        )

    def cancel(self, order_id: int) -> None:
        self._post(f"/internal/inventory/reservations/{order_id}/cancel", {})

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = self.client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise InventoryServiceError("INVENTORY_SERVICE_UNAVAILABLE", "库存服务暂不可用", 503) from exc

        if response.is_success:
            if response.content:
                return response.json()
            return {}

        detail = {}
        try:
            detail = response.json()
        except ValueError:
            detail = {}
        raise InventoryServiceError(
            detail.get("code", "INVENTORY_REQUEST_FAILED"),
            detail.get("message", "库存服务请求失败"),
            response.status_code,
        )


class OrderApplicationService:
    def __init__(
        self,
        order_db: Session,
        product_db: Session,
        inventory_client: InventoryServiceClient,
        id_generator: SnowflakeIdGenerator,
    ) -> None:
        self.order_repository = OrderRepository(order_db)
        self.product_repository = ProductRepository(product_db)
        self.inventory_client = inventory_client
        self.id_generator = id_generator

    def submit_seckill_order(
        self,
        request: SeckillOrderRequest,
        current_user: CurrentUser,
    ) -> SeckillOrderAcceptedResponse:
        existing_order = self.order_repository.find_active_by_user_and_product(
            user_id=current_user.user_id,
            product_id=request.product_id,
        )
        if existing_order:
            raise BusinessException("DUPLICATE_ORDER", "同一用户同一商品只能秒杀一次", 409)

        product = self.product_repository.get_product(request.product_id)
        if product is None:
            raise BusinessException("PRODUCT_NOT_FOUND", "秒杀商品不存在", 404)

        order_id = self.id_generator.next_id()
        try:
            self.inventory_client.reserve(
                order_id=order_id,
                user_id=current_user.user_id,
                product_id=request.product_id,
                quantity=request.quantity,
            )
        except InventoryServiceError as exc:
            raise BusinessException(exc.code, exc.message, exc.status_code) from exc

        event = OrderCreatedEvent(
            order_id=order_id,
            user_id=current_user.user_id,
            product_id=request.product_id,
            quantity=request.quantity,
            unit_price=Decimal(str(product.price)),
            total_amount=Decimal(str(product.price)) * request.quantity,
        )

        try:
            self.order_repository.create_pending_order_and_outbox(event)
        except IntegrityError as exc:
            self.order_repository.session.rollback()
            try:
                self.inventory_client.cancel(order_id)
            except InventoryServiceError:
                logger.error(
                    "failed to cancel inventory reservation after duplicate order",
                    extra={"event": "inventory_cancel_failed", "order_id": order_id},
                )
            raise BusinessException("DUPLICATE_ORDER", "同一用户同一商品只能秒杀一次", 409) from exc
        except Exception:
            self.order_repository.session.rollback()
            try:
                self.inventory_client.cancel(order_id)
            except InventoryServiceError:
                logger.error(
                    "failed to cancel inventory reservation after order persistence error",
                    extra={"event": "inventory_cancel_failed", "order_id": order_id},
                )
            raise

        logger.info(
            "seckill order accepted",
            extra={
                "event": "seckill_order_accepted",
                "order_id": order_id,
                "user_id": current_user.user_id,
                "product_id": request.product_id,
                "outcome": "pending_inventory",
            },
        )
        return SeckillOrderAcceptedResponse(
            order_id=order_id,
            status="PENDING_INVENTORY",
            message="订单已创建并预扣库存，等待库存服务异步确认",
        )

    def pay_order(
        self,
        order_id: int,
        request: PaymentRequest,
        current_user: CurrentUser,
    ) -> PaymentAcceptedResponse:
        order = self.order_repository.get_by_order_id(order_id=order_id, user_id=current_user.user_id)
        if order is None:
            raise BusinessException("ORDER_NOT_FOUND", "订单不存在", 404)
        if order.status == "FAILED":
            raise BusinessException("ORDER_FAILED", "失败订单不能支付", 409)
        if order.status == "PENDING_INVENTORY":
            raise BusinessException("ORDER_NOT_READY", "库存尚未确认，请稍后再支付", 409)

        amount = request.amount or Decimal(order.total_amount)
        if amount != Decimal(order.total_amount):
            raise BusinessException("INVALID_PAYMENT_AMOUNT", "支付金额必须与订单金额一致", 409)

        order_status, payment_status = self.order_repository.request_payment(order=order, amount=amount)
        logger.info(
            "order payment accepted",
            extra={
                "event": "order_payment_accepted",
                "order_id": order_id,
                "user_id": current_user.user_id,
                "order_status": order_status,
                "payment_status": payment_status,
            },
        )
        return PaymentAcceptedResponse(
            order_id=order_id,
            payment_status=payment_status,
            order_status=order_status,
            message="支付请求已受理，订单状态将异步更新",
        )


class KafkaEventProducer:
    def __init__(self) -> None:
        self._producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        )

    def send(self, topic: str, payload: dict) -> None:
        self._producer.send(topic, payload)
        self._producer.flush()


def ensure_topics_exist() -> None:
    admin_client = KafkaAdminClient(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
    topics = [
        settings.KAFKA_ORDER_CREATED_TOPIC,
        settings.KAFKA_INVENTORY_RESULT_TOPIC,
        settings.KAFKA_PAYMENT_TOPIC,
    ]
    try:
        admin_client.create_topics(
            new_topics=[NewTopic(name=name, num_partitions=1, replication_factor=1) for name in topics],
            validate_only=False,
        )
    except TopicAlreadyExistsError:
        return
    finally:
        admin_client.close()


class OrderOutboxPublisher:
    def __init__(self, order_session_factory) -> None:
        self.order_session_factory = order_session_factory
        self.producer = KafkaEventProducer()

    def run(self) -> None:
        logger.info("order outbox publisher started", extra={"event": "order_outbox_started"})
        while True:
            session = self.order_session_factory()
            try:
                repository = OrderRepository(session)
                events = repository.list_pending_outbox_events(settings.OUTBOX_PUBLISH_BATCH_SIZE)
            finally:
                session.close()

            if not events:
                time.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)
                continue

            for event in events:
                session = self.order_session_factory()
                try:
                    repository = OrderRepository(session)
                    payload = json.loads(event.payload)
                    self.producer.send(event.topic, payload)
                    repository.mark_outbox_published(event)
                except Exception:
                    session.rollback()
                    retry_session = self.order_session_factory()
                    try:
                        OrderRepository(retry_session).mark_outbox_retry(event)
                    finally:
                        retry_session.close()
                finally:
                    session.close()


class InventoryResultConsumer:
    def __init__(self, order_session_factory) -> None:
        self.order_session_factory = order_session_factory
        self.consumer = KafkaConsumer(
            settings.KAFKA_INVENTORY_RESULT_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_INVENTORY_RESULT_GROUP_ID,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

    def run(self) -> None:
        logger.info(
            "inventory result consumer started",
            extra={"event": "order_inventory_result_consumer_started"},
        )
        for message in self.consumer:
            payload = InventoryResultEvent.model_validate(message.value)
            session = self.order_session_factory()
            try:
                repository = OrderRepository(session)
                if payload.status == "CONFIRMED":
                    repository.mark_inventory_confirmed(payload)
                else:
                    repository.mark_inventory_failed(payload)
                self.consumer.commit()
            finally:
                session.close()


class PaymentResultConsumer:
    def __init__(self, order_session_factory) -> None:
        self.order_session_factory = order_session_factory
        self.consumer = KafkaConsumer(
            settings.KAFKA_PAYMENT_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_PAYMENT_GROUP_ID,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

    def run(self) -> None:
        logger.info("payment consumer started", extra={"event": "order_payment_consumer_started"})
        for message in self.consumer:
            payload = PaymentRequestedEvent.model_validate(message.value)
            session = self.order_session_factory()
            try:
                repository = OrderRepository(session)
                repository.mark_payment_success(payload)
                self.consumer.commit()
            finally:
                session.close()


class OrderWorker:
    def __init__(self, order_session_factory) -> None:
        self.publisher = OrderOutboxPublisher(order_session_factory=order_session_factory)
        self.inventory_result_consumer = InventoryResultConsumer(order_session_factory=order_session_factory)
        self.payment_result_consumer = PaymentResultConsumer(order_session_factory=order_session_factory)

    def run(self) -> None:
        threads = [
            threading.Thread(target=self.publisher.run, name="order-outbox-publisher", daemon=True),
            threading.Thread(
                target=self.inventory_result_consumer.run,
                name="inventory-result-consumer",
                daemon=True,
            ),
            threading.Thread(
                target=self.payment_result_consumer.run,
                name="payment-result-consumer",
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
