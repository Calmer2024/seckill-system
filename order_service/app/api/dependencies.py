from typing import Annotated

import redis
from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.order_service import (
    KafkaOrderProducer,
    OrderApplicationService,
    SnowflakeIdGenerator,
)
from app.core.config import settings
from app.core.database import get_order_db, get_product_db, get_redis_client


producer = KafkaOrderProducer()
id_generator = SnowflakeIdGenerator(
    datacenter_id=settings.SNOWFLAKE_DATACENTER_ID,
    worker_id=settings.SNOWFLAKE_WORKER_ID,
    epoch_milliseconds=settings.SNOWFLAKE_EPOCH_MILLISECONDS,
)


def get_order_application_service(
    order_db: Annotated[Session, Depends(get_order_db)],
    product_db: Annotated[Session, Depends(get_product_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis_client)],
) -> OrderApplicationService:
    return OrderApplicationService(
        order_db=order_db,
        product_db=product_db,
        redis_client=redis_client,
        producer=producer,
        id_generator=id_generator,
    )
