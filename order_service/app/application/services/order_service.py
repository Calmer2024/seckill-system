import json
import threading
import time
from decimal import Decimal

import redis
from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.dto.order_dto import OrderEvent, SeckillOrderAcceptedResponse, SeckillOrderRequest
from app.core.config import settings
from app.core.exceptions.business_exception import BusinessException
from app.core.security import CurrentUser
from app.infrastructure.logging.logger import get_logger
from app.models.order import Order, UserPurchaseRecord
from app.models.product import Product


logger = get_logger(__name__)

RESERVE_STOCK_SCRIPT = """
local stock_key = KEYS[1]
local user_key = KEYS[2]
local status_key = KEYS[3]
local owner_key = KEYS[4]
local quantity = tonumber(ARGV[1])
local order_id = ARGV[2]
local status = ARGV[3]
local ttl = tonumber(ARGV[4])

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
redis.call('set', status_key, status, 'EX', ttl)
redis.call('set', owner_key, ARGV[5], 'EX', ttl)
return 1
"""

RELEASE_RESERVATION_SCRIPT = """
local user_key = KEYS[1]
local stock_key = KEYS[2]
local status_key = KEYS[3]
local owner_key = KEYS[4]
local order_id = ARGV[1]
local quantity = tonumber(ARGV[2])
local status = ARGV[3]
local ttl = tonumber(ARGV[4])

if redis.call('get', user_key) == order_id then
    redis.call('del', user_key)
    redis.call('incrby', stock_key, quantity)
end

redis.call('set', status_key, status, 'EX', ttl)
redis.call('del', owner_key)
return 1
"""


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


class StockCacheService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis_client = redis_client
        self.reserve_script = redis_client.register_script(RESERVE_STOCK_SCRIPT)
        self.release_script = redis_client.register_script(RELEASE_RESERVATION_SCRIPT)

    @staticmethod
    def stock_key(product_id: int) -> str:
        return f"seckill:stock:{product_id}"

    @staticmethod
    def user_purchase_key(user_id: int, product_id: int) -> str:
        return f"seckill:user:{user_id}:product:{product_id}"

    @staticmethod
    def order_status_key(order_id: int) -> str:
        return f"seckill:order:status:{order_id}"

    @staticmethod
    def order_owner_key(order_id: int) -> str:
        return f"seckill:order:owner:{order_id}"

    def ensure_stock_loaded(self, product: Product) -> None:
        key = self.stock_key(product.id)
        if self.redis_client.exists(key):
            return
        self.redis_client.set(key, int(product.stock))

    def reserve_stock(self, user_id: int, product_id: int, order_id: int, quantity: int) -> int:
        return int(
            self.reserve_script(
                keys=[
                    self.stock_key(product_id),
                    self.user_purchase_key(user_id, product_id),
                    self.order_status_key(order_id),
                    self.order_owner_key(order_id),
                ],
                args=[
                    quantity,
                    str(order_id),
                    "QUEUED",
                    settings.SECKILL_RESERVATION_TTL_SECONDS,
                    str(user_id),
                ],
            )
        )

    def release_reservation(self, user_id: int, product_id: int, order_id: int, quantity: int) -> None:
        self.release_script(
            keys=[
                self.user_purchase_key(user_id, product_id),
                self.stock_key(product_id),
                self.order_status_key(order_id),
                self.order_owner_key(order_id),
            ],
            args=[
                str(order_id),
                quantity,
                "FAILED",
                settings.ORDER_STATUS_TTL_SECONDS,
            ],
        )

    def mark_success(self, user_id: int, product_id: int, order_id: int) -> None:
        pipeline = self.redis_client.pipeline()
        pipeline.set(
            self.order_status_key(order_id),
            "SUCCESS",
            ex=settings.ORDER_STATUS_TTL_SECONDS,
        )
        pipeline.set(
            self.user_purchase_key(user_id, product_id),
            str(order_id),
            ex=settings.ORDER_STATUS_TTL_SECONDS,
        )
        pipeline.set(
            self.order_owner_key(order_id),
            str(user_id),
            ex=settings.ORDER_STATUS_TTL_SECONDS,
        )
        pipeline.execute()

    def get_order_status(self, order_id: int) -> str | None:
        return self.redis_client.get(self.order_status_key(order_id))

    def get_order_owner(self, order_id: int) -> int | None:
        owner = self.redis_client.get(self.order_owner_key(order_id))
        return int(owner) if owner else None


class KafkaOrderProducer:
    def __init__(self) -> None:
        self._producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        )

    def send(self, event: OrderEvent) -> None:
        self._producer.send(settings.KAFKA_ORDER_TOPIC, event.model_dump(mode="json"))
        self._producer.flush()


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

    def find_by_user_and_product(self, user_id: int, product_id: int) -> Order | None:
        statement = (
            select(Order)
            .where(Order.user_id == user_id, Order.product_id == product_id)
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def create_order(self, event: OrderEvent) -> Order:
        order = Order(
            order_id=event.order_id,
            user_id=event.user_id,
            product_id=event.product_id,
            quantity=event.quantity,
            unit_price=event.unit_price,
            total_amount=event.unit_price * event.quantity,
            status="SUCCESS",
        )
        purchase_record = UserPurchaseRecord(
            user_id=event.user_id,
            product_id=event.product_id,
            order_id=event.order_id,
        )
        self.session.add(purchase_record)
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        return order


class InventoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_product(self, product_id: int) -> Product | None:
        statement = select(Product).where(Product.id == product_id)
        return self.session.execute(statement).scalar_one_or_none()

    def deduct_stock(self, product_id: int, quantity: int) -> bool:
        statement = (
            update(Product)
            .where(Product.id == product_id, Product.stock >= quantity)
            .values(stock=Product.stock - quantity)
        )
        result = self.session.execute(statement)
        if result.rowcount == 0:
            self.session.rollback()
            return False
        self.session.commit()
        return True

    def restore_stock(self, product_id: int, quantity: int) -> None:
        statement = update(Product).where(Product.id == product_id).values(stock=Product.stock + quantity)
        self.session.execute(statement)
        self.session.commit()


class OrderApplicationService:
    def __init__(
        self,
        order_db: Session,
        product_db: Session,
        redis_client: redis.Redis,
        producer: KafkaOrderProducer,
        id_generator: SnowflakeIdGenerator,
    ) -> None:
        self.order_repository = OrderRepository(order_db)
        self.inventory_repository = InventoryRepository(product_db)
        self.stock_cache_service = StockCacheService(redis_client)
        self.producer = producer
        self.id_generator = id_generator

    def submit_seckill_order(
        self,
        request: SeckillOrderRequest,
        current_user: CurrentUser,
    ) -> SeckillOrderAcceptedResponse:
        existing_order = self.order_repository.find_by_user_and_product(
            user_id=current_user.user_id,
            product_id=request.product_id,
        )
        if existing_order:
            raise BusinessException("DUPLICATE_ORDER", "同一用户同一商品只能秒杀一次", 409)

        product = self.inventory_repository.get_product(request.product_id)
        if product is None:
            raise BusinessException("PRODUCT_NOT_FOUND", "秒杀商品不存在", 404)

        self.stock_cache_service.ensure_stock_loaded(product)

        order_id = self.id_generator.next_id()
        reserve_result = self.stock_cache_service.reserve_stock(
            user_id=current_user.user_id,
            product_id=request.product_id,
            order_id=order_id,
            quantity=request.quantity,
        )

        if reserve_result == 2:
            raise BusinessException("DUPLICATE_ORDER", "同一用户同一商品只能秒杀一次", 409)
        if reserve_result == 0:
            raise BusinessException("OUT_OF_STOCK", "商品已售罄", 409)
        if reserve_result == -1:
            raise BusinessException("STOCK_NOT_READY", "库存缓存尚未就绪，请稍后重试", 503)

        event = OrderEvent(
            order_id=order_id,
            user_id=current_user.user_id,
            product_id=request.product_id,
            quantity=request.quantity,
            unit_price=Decimal(str(product.price)),
        )

        try:
            self.producer.send(event)
        except Exception as exc:
            self.stock_cache_service.release_reservation(
                user_id=current_user.user_id,
                product_id=request.product_id,
                order_id=order_id,
                quantity=request.quantity,
            )
            raise BusinessException("MQ_UNAVAILABLE", "下单请求排队失败，请稍后重试", 503) from exc

        logger.info(
            "seckill order accepted",
            extra={
                "event": "seckill_order_accepted",
                "order_id": order_id,
                "user_id": current_user.user_id,
                "product_id": request.product_id,
                "outcome": "queued",
            },
        )
        return SeckillOrderAcceptedResponse(
            order_id=order_id,
            status="QUEUED",
            message="下单请求已进入队列，请稍后查询订单结果",
        )


def ensure_order_topic_exists() -> None:
    admin_client = KafkaAdminClient(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
    try:
        admin_client.create_topics(
            new_topics=[
                NewTopic(
                    name=settings.KAFKA_ORDER_TOPIC,
                    num_partitions=1,
                    replication_factor=1,
                )
            ],
            validate_only=False,
        )
    except TopicAlreadyExistsError:
        return
    finally:
        admin_client.close()


class OrderWorker:
    def __init__(
        self,
        order_session_factory,
        product_session_factory,
        redis_client: redis.Redis,
    ) -> None:
        self.order_session_factory = order_session_factory
        self.product_session_factory = product_session_factory
        self.stock_cache_service = StockCacheService(redis_client)
        self.consumer = KafkaConsumer(
            settings.KAFKA_ORDER_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP_ID,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

    def run(self) -> None:
        logger.info(
            "order worker started",
            extra={"event": "order_worker_started", "topic": settings.KAFKA_ORDER_TOPIC},
        )
        for message in self.consumer:
            payload = OrderEvent.model_validate(message.value)
            self._handle_message(payload)
            self.consumer.commit()

    def _handle_message(self, payload: OrderEvent) -> None:
        order_db = self.order_session_factory()
        product_db = self.product_session_factory()

        try:
            order_repository = OrderRepository(order_db)
            inventory_repository = InventoryRepository(product_db)

            existing_order = order_repository.find_by_user_and_product(payload.user_id, payload.product_id)
            if existing_order:
                self.stock_cache_service.mark_success(
                    user_id=payload.user_id,
                    product_id=payload.product_id,
                    order_id=existing_order.order_id,
                )
                logger.info(
                    "duplicate event ignored because order already exists",
                    extra={
                        "event": "order_duplicate_event",
                        "order_id": existing_order.order_id,
                        "user_id": payload.user_id,
                        "product_id": payload.product_id,
                        "outcome": "already_exists",
                    },
                )
                return

            if not inventory_repository.deduct_stock(payload.product_id, payload.quantity):
                self.stock_cache_service.release_reservation(
                    user_id=payload.user_id,
                    product_id=payload.product_id,
                    order_id=payload.order_id,
                    quantity=payload.quantity,
                )
                logger.info(
                    "order rejected because stock is insufficient in database",
                    extra={
                        "event": "order_stock_rejected",
                        "order_id": payload.order_id,
                        "user_id": payload.user_id,
                        "product_id": payload.product_id,
                        "outcome": "out_of_stock",
                    },
                )
                return

            try:
                order_repository.create_order(payload)
                self.stock_cache_service.mark_success(
                    user_id=payload.user_id,
                    product_id=payload.product_id,
                    order_id=payload.order_id,
                )
                logger.info(
                    "order created successfully",
                    extra={
                        "event": "order_created",
                        "order_id": payload.order_id,
                        "user_id": payload.user_id,
                        "product_id": payload.product_id,
                        "outcome": "success",
                    },
                )
            except IntegrityError:
                order_db.rollback()
                inventory_repository.restore_stock(payload.product_id, payload.quantity)
                self.stock_cache_service.release_reservation(
                    user_id=payload.user_id,
                    product_id=payload.product_id,
                    order_id=payload.order_id,
                    quantity=payload.quantity,
                )
                logger.info(
                    "order creation rolled back because duplicate purchase was detected",
                    extra={
                        "event": "order_duplicate_purchase",
                        "order_id": payload.order_id,
                        "user_id": payload.user_id,
                        "product_id": payload.product_id,
                        "outcome": "rolled_back",
                    },
                )
            except Exception:
                order_db.rollback()
                inventory_repository.restore_stock(payload.product_id, payload.quantity)
                self.stock_cache_service.release_reservation(
                    user_id=payload.user_id,
                    product_id=payload.product_id,
                    order_id=payload.order_id,
                    quantity=payload.quantity,
                )
                raise
        finally:
            order_db.close()
            product_db.close()
