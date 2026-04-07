import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import redis
from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions.business_exception import BusinessException
from app.infrastructure.logging.logger import get_logger
from app.models.inventory import InventoryItem, InventoryOutboxEvent, InventoryReservation
from app.schemas.inventory import InventoryReservationRequest, InventoryReservationResponse, InventoryResultEvent


logger = get_logger(__name__)

RESERVE_STOCK_SCRIPT = """
local stock_key = KEYS[1]
local user_key = KEYS[2]
local reservation_key = KEYS[3]
local quantity = tonumber(ARGV[1])
local order_id = ARGV[2]
local ttl = tonumber(ARGV[3])

if redis.call('exists', user_key) == 1 then
    return 2
end

local stock = redis.call('get', stock_key)
if not stock then
    return -1
end

stock = tonumber(stock)
if stock < quantity then
    return 0
end

redis.call('decrby', stock_key, quantity)
redis.call('set', user_key, order_id, 'EX', ttl)
redis.call('set', reservation_key, 'RESERVED', 'EX', ttl)
return 1
"""

RELEASE_STOCK_SCRIPT = """
local user_key = KEYS[1]
local stock_key = KEYS[2]
local reservation_key = KEYS[3]
local order_id = ARGV[1]
local quantity = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

if redis.call('get', user_key) == order_id then
    redis.call('del', user_key)
    redis.call('incrby', stock_key, quantity)
end

redis.call('set', reservation_key, 'CANCELED', 'EX', ttl)
return 1
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ReservationSnapshot:
    order_id: int
    user_id: int
    product_id: int
    quantity: int
    status: str
    failure_reason: str | None = None


class StockCacheService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis_client = redis_client
        self.reserve_script = redis_client.register_script(RESERVE_STOCK_SCRIPT)
        self.release_script = redis_client.register_script(RELEASE_STOCK_SCRIPT)

    @staticmethod
    def stock_key(product_id: int) -> str:
        return f"seckill:stock:{product_id}"

    @staticmethod
    def user_purchase_key(user_id: int, product_id: int) -> str:
        return f"seckill:user:{user_id}:product:{product_id}"

    @staticmethod
    def reservation_status_key(order_id: int) -> str:
        return f"seckill:reservation:{order_id}"

    def ensure_stock_loaded(self, item: InventoryItem) -> None:
        if self.redis_client.exists(self.stock_key(item.product_id)):
            return
        self.redis_client.set(self.stock_key(item.product_id), int(item.available_stock))

    def reserve_stock(self, user_id: int, product_id: int, order_id: int, quantity: int) -> int:
        return int(
            self.reserve_script(
                keys=[
                    self.stock_key(product_id),
                    self.user_purchase_key(user_id, product_id),
                    self.reservation_status_key(order_id),
                ],
                args=[quantity, str(order_id), settings.SECKILL_RESERVATION_TTL_SECONDS],
            )
        )

    def release_stock(self, user_id: int, product_id: int, order_id: int, quantity: int) -> None:
        self.release_script(
            keys=[
                self.user_purchase_key(user_id, product_id),
                self.stock_key(product_id),
                self.reservation_status_key(order_id),
            ],
            args=[str(order_id), quantity, settings.ORDER_STATUS_TTL_SECONDS],
        )

    def mark_confirmed(self, user_id: int, product_id: int, order_id: int) -> None:
        pipeline = self.redis_client.pipeline()
        pipeline.set(
            self.user_purchase_key(user_id, product_id),
            str(order_id),
            ex=settings.ORDER_STATUS_TTL_SECONDS,
        )
        pipeline.set(
            self.reservation_status_key(order_id),
            "CONFIRMED",
            ex=settings.ORDER_STATUS_TTL_SECONDS,
        )
        pipeline.execute()


class InventoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_item(self, product_id: int) -> InventoryItem | None:
        return self.session.execute(
            select(InventoryItem).where(InventoryItem.product_id == product_id)
        ).scalar_one_or_none()

    def find_active_user_reservation(self, user_id: int, product_id: int) -> InventoryReservation | None:
        statement = (
            select(InventoryReservation)
            .where(
                InventoryReservation.user_id == user_id,
                InventoryReservation.product_id == product_id,
                InventoryReservation.status.in_(["RESERVED", "CONFIRMED"]),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_reservation(self, order_id: int) -> InventoryReservation | None:
        return self.session.execute(
            select(InventoryReservation).where(InventoryReservation.order_id == order_id)
        ).scalar_one_or_none()

    def create_reservation(self, order_id: int, user_id: int, product_id: int, quantity: int) -> ReservationSnapshot:
        existing = self.get_reservation(order_id)
        if existing is not None:
            self.session.rollback()
            return ReservationSnapshot(
                order_id=existing.order_id,
                user_id=existing.user_id,
                product_id=existing.product_id,
                quantity=existing.quantity,
                status=existing.status,
                failure_reason=existing.failure_reason,
            )

        item = self.get_item(product_id)
        if item is None:
            self.session.rollback()
            raise BusinessException("PRODUCT_NOT_FOUND", "库存商品不存在", 404)
        if item.available_stock < quantity:
            self.session.rollback()
            raise BusinessException("OUT_OF_STOCK", "商品已售罄", 409)

        item.available_stock -= quantity
        item.reserved_stock += quantity
        item.version += 1
        self.session.add(
            InventoryReservation(
                order_id=order_id,
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                status="RESERVED",
            )
        )
        self.session.commit()
        return ReservationSnapshot(order_id, user_id, product_id, quantity, "RESERVED")

    def cancel_reservation(self, order_id: int) -> ReservationSnapshot | None:
        reservation = self.get_reservation(order_id)
        if reservation is None:
            self.session.rollback()
            return None
        if reservation.status != "RESERVED":
            self.session.rollback()
            return ReservationSnapshot(
                order_id=reservation.order_id,
                user_id=reservation.user_id,
                product_id=reservation.product_id,
                quantity=reservation.quantity,
                status=reservation.status,
                failure_reason=reservation.failure_reason,
            )

        item = self.get_item(reservation.product_id)
        if item is None:
            self.session.rollback()
            raise BusinessException("PRODUCT_NOT_FOUND", "库存商品不存在", 404)

        item.available_stock += reservation.quantity
        item.reserved_stock -= reservation.quantity
        item.version += 1
        reservation.status = "CANCELED"
        reservation.failure_reason = "ORDER_ROLLED_BACK"
        self.session.commit()
        return ReservationSnapshot(
            order_id=reservation.order_id,
            user_id=reservation.user_id,
            product_id=reservation.product_id,
            quantity=reservation.quantity,
            status=reservation.status,
            failure_reason=reservation.failure_reason,
        )

    def confirm_reservation_and_enqueue_result(self, payload: InventoryResultEvent) -> ReservationSnapshot:
        reservation = self.get_reservation(payload.order_id)
        if reservation is None:
            return self._enqueue_result(
                InventoryResultEvent(
                    order_id=payload.order_id,
                    user_id=payload.user_id,
                    product_id=payload.product_id,
                    quantity=payload.quantity,
                    status="FAILED",
                    failure_reason="RESERVATION_NOT_FOUND",
                )
            )

        if reservation.status == "CONFIRMED":
            self.session.rollback()
            return ReservationSnapshot(
                order_id=reservation.order_id,
                user_id=reservation.user_id,
                product_id=reservation.product_id,
                quantity=reservation.quantity,
                status=reservation.status,
                failure_reason=reservation.failure_reason,
            )

        if reservation.status != "RESERVED":
            return self._enqueue_result(
                InventoryResultEvent(
                    order_id=reservation.order_id,
                    user_id=reservation.user_id,
                    product_id=reservation.product_id,
                    quantity=reservation.quantity,
                    status="FAILED",
                    failure_reason=reservation.failure_reason or reservation.status,
                )
            )

        item = self.get_item(reservation.product_id)
        if item is None:
            self.session.rollback()
            raise BusinessException("PRODUCT_NOT_FOUND", "库存商品不存在", 404)

        item.reserved_stock -= reservation.quantity
        item.sold_stock += reservation.quantity
        item.version += 1
        reservation.status = "CONFIRMED"
        reservation.failure_reason = None
        event = InventoryResultEvent(
            order_id=reservation.order_id,
            user_id=reservation.user_id,
            product_id=reservation.product_id,
            quantity=reservation.quantity,
            status="CONFIRMED",
        )
        self.session.add(
            InventoryOutboxEvent(
                aggregate_id=reservation.order_id,
                topic=settings.KAFKA_INVENTORY_RESULT_TOPIC,
                event_type="INVENTORY_CONFIRMED",
                payload=json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
                status="NEW",
            )
        )
        self.session.commit()
        return ReservationSnapshot(
            order_id=reservation.order_id,
            user_id=reservation.user_id,
            product_id=reservation.product_id,
            quantity=reservation.quantity,
            status="CONFIRMED",
        )

    def _enqueue_result(self, event: InventoryResultEvent) -> ReservationSnapshot:
        self.session.add(
            InventoryOutboxEvent(
                aggregate_id=event.order_id,
                topic=settings.KAFKA_INVENTORY_RESULT_TOPIC,
                event_type="INVENTORY_RESERVATION_FAILED",
                payload=json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
                status="NEW",
            )
        )
        self.session.commit()
        return ReservationSnapshot(
            order_id=event.order_id,
            user_id=event.user_id,
            product_id=event.product_id,
            quantity=event.quantity,
            status=event.status,
            failure_reason=event.failure_reason,
        )

    def list_pending_outbox_events(self, limit: int) -> list[InventoryOutboxEvent]:
        statement = (
            select(InventoryOutboxEvent)
            .where(
                InventoryOutboxEvent.status.in_(["NEW", "RETRY"]),
                or_(InventoryOutboxEvent.next_retry_at.is_(None), InventoryOutboxEvent.next_retry_at <= utcnow()),
            )
            .order_by(InventoryOutboxEvent.id.asc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def mark_outbox_published(self, event_id: int) -> None:
        event = self.session.get(InventoryOutboxEvent, event_id)
        if event is None:
            self.session.rollback()
            return
        event.status = "PUBLISHED"
        event.published_at = utcnow()
        self.session.commit()

    def mark_outbox_retry(self, event_id: int) -> None:
        event = self.session.get(InventoryOutboxEvent, event_id)
        if event is None:
            self.session.rollback()
            return
        retry_count = event.retry_count + 1
        event.retry_count = retry_count
        event.status = "RETRY"
        event.next_retry_at = utcnow() + timedelta(seconds=min(retry_count * 2, 30))
        self.session.commit()


class InventoryApplicationService:
    def __init__(self, inventory_db: Session, redis_client: redis.Redis) -> None:
        self.repository = InventoryRepository(inventory_db)
        self.stock_cache = StockCacheService(redis_client)

    def get_inventory_item(self, product_id: int) -> InventoryItem:
        item = self.repository.get_item(product_id)
        if item is None:
            raise BusinessException("PRODUCT_NOT_FOUND", "库存商品不存在", 404)
        return item

    def reserve_inventory(self, request: InventoryReservationRequest) -> InventoryReservationResponse:
        existing = self.repository.find_active_user_reservation(request.user_id, request.product_id)
        if existing and existing.order_id != request.order_id:
            raise BusinessException("DUPLICATE_ORDER", "同一用户同一商品只能秒杀一次", 409)

        item = self.repository.get_item(request.product_id)
        if item is None:
            raise BusinessException("PRODUCT_NOT_FOUND", "库存商品不存在", 404)
        self.stock_cache.ensure_stock_loaded(item)

        reserve_result = self.stock_cache.reserve_stock(
            user_id=request.user_id,
            product_id=request.product_id,
            order_id=request.order_id,
            quantity=request.quantity,
        )
        if reserve_result == 2:
            raise BusinessException("DUPLICATE_ORDER", "同一用户同一商品只能秒杀一次", 409)
        if reserve_result == 0:
            raise BusinessException("OUT_OF_STOCK", "商品已售罄", 409)
        if reserve_result == -1:
            raise BusinessException("STOCK_NOT_READY", "库存缓存尚未就绪，请稍后重试", 503)

        try:
            snapshot = self.repository.create_reservation(
                order_id=request.order_id,
                user_id=request.user_id,
                product_id=request.product_id,
                quantity=request.quantity,
            )
        except Exception:
            self.repository.session.rollback()
            self.stock_cache.release_stock(
                user_id=request.user_id,
                product_id=request.product_id,
                order_id=request.order_id,
                quantity=request.quantity,
            )
            raise

        logger.info(
            "inventory reserved",
            extra={
                "event": "inventory_reserved",
                "order_id": snapshot.order_id,
                "user_id": snapshot.user_id,
                "product_id": snapshot.product_id,
                "outcome": snapshot.status,
            },
        )
        return InventoryReservationResponse(
            order_id=request.order_id,
            status=snapshot.status,
            message="库存预扣减成功，等待订单服务确认",
        )

    def cancel_inventory_reservation(self, order_id: int) -> InventoryReservationResponse:
        snapshot = self.repository.cancel_reservation(order_id)
        if snapshot is None:
            return InventoryReservationResponse(order_id=order_id, status="NOT_FOUND", message="库存预留不存在")
        if snapshot.status == "CANCELED":
            self.stock_cache.release_stock(
                user_id=snapshot.user_id,
                product_id=snapshot.product_id,
                order_id=snapshot.order_id,
                quantity=snapshot.quantity,
            )
            return InventoryReservationResponse(
                order_id=snapshot.order_id,
                status="CANCELED",
                message="库存预留已取消并回补",
            )
        return InventoryReservationResponse(
            order_id=snapshot.order_id,
            status=snapshot.status,
            message="库存预留已是最终状态，无需重复取消",
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
    topics = [settings.KAFKA_ORDER_CREATED_TOPIC, settings.KAFKA_INVENTORY_RESULT_TOPIC]
    try:
        admin_client.create_topics(
            new_topics=[NewTopic(name=name, num_partitions=1, replication_factor=1) for name in topics],
            validate_only=False,
        )
    except TopicAlreadyExistsError:
        return
    finally:
        admin_client.close()


class InventoryOutboxPublisher:
    def __init__(self, inventory_session_factory) -> None:
        self.inventory_session_factory = inventory_session_factory
        self.producer = KafkaEventProducer()

    def run(self) -> None:
        logger.info("inventory outbox publisher started", extra={"event": "inventory_outbox_started"})
        while True:
            session = self.inventory_session_factory()
            try:
                events = InventoryRepository(session).list_pending_outbox_events(settings.OUTBOX_PUBLISH_BATCH_SIZE)
            finally:
                session.close()

            if not events:
                time.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)
                continue

            for event in events:
                session = self.inventory_session_factory()
                try:
                    self.producer.send(event.topic, json.loads(event.payload))
                    InventoryRepository(session).mark_outbox_published(event.id)
                except Exception:
                    session.rollback()
                    retry_session = self.inventory_session_factory()
                    try:
                        InventoryRepository(retry_session).mark_outbox_retry(event.id)
                    finally:
                        retry_session.close()
                finally:
                    session.close()


class OrderCreatedConsumer:
    def __init__(self, inventory_session_factory, redis_client: redis.Redis) -> None:
        self.inventory_session_factory = inventory_session_factory
        self.stock_cache = StockCacheService(redis_client)
        self.consumer = KafkaConsumer(
            settings.KAFKA_ORDER_CREATED_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_ORDER_CREATED_GROUP_ID,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

    def run(self) -> None:
        logger.info("order created consumer started", extra={"event": "inventory_order_created_consumer_started"})
        for message in self.consumer:
            payload = InventoryResultEvent(
                order_id=message.value["order_id"],
                user_id=message.value["user_id"],
                product_id=message.value["product_id"],
                quantity=message.value["quantity"],
                status="RESERVED",
            )
            session = self.inventory_session_factory()
            try:
                snapshot = InventoryRepository(session).confirm_reservation_and_enqueue_result(payload)
                if snapshot.status == "CONFIRMED":
                    self.stock_cache.mark_confirmed(
                        user_id=snapshot.user_id,
                        product_id=snapshot.product_id,
                        order_id=snapshot.order_id,
                    )
                self.consumer.commit()
            finally:
                session.close()


class InventoryWorker:
    def __init__(self, inventory_session_factory, redis_client: redis.Redis) -> None:
        self.publisher = InventoryOutboxPublisher(inventory_session_factory=inventory_session_factory)
        self.consumer = OrderCreatedConsumer(
            inventory_session_factory=inventory_session_factory,
            redis_client=redis_client,
        )

    def run(self) -> None:
        threads = [
            threading.Thread(target=self.publisher.run, name="inventory-outbox-publisher", daemon=True),
            threading.Thread(target=self.consumer.run, name="inventory-order-created-consumer", daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
