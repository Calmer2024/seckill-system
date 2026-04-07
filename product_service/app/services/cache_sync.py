# 兼容旧引用，真正的缓存预热逻辑已收敛到应用服务层。
from sqlalchemy.orm import Session

from app.application.services.product_query_service_impl import ProductQueryServiceImpl
from app.core.database import redis_client
from app.infrastructure.cache.redis_cache_service import RedisCacheService
from app.infrastructure.database.product_repository import SqlAlchemyProductRepository


def prewarm_products_to_cache(db: Session) -> dict:
    service = ProductQueryServiceImpl(
        product_repository=SqlAlchemyProductRepository(read_session=db, write_session=db),
        cache_service=RedisCacheService(redis_client=redis_client),
    )
    return service.prewarm_cache().model_dump()
