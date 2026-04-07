from typing import Annotated

import redis
from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.interfaces.product_query_service import ProductQueryService
from app.application.services.product_query_service_impl import ProductQueryServiceImpl
from app.core.database import get_read_db, get_redis_client, get_write_db
from app.infrastructure.cache.redis_cache_service import RedisCacheService
from app.infrastructure.database.product_repository import SqlAlchemyProductRepository


def get_product_query_service(
    read_db: Annotated[Session, Depends(get_read_db)],
    write_db: Annotated[Session, Depends(get_write_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis_client)],
) -> ProductQueryService:
    return ProductQueryServiceImpl(
        product_repository=SqlAlchemyProductRepository(
            read_session=read_db,
            write_session=write_db,
        ),
        cache_service=RedisCacheService(redis_client=redis_client),
    )
