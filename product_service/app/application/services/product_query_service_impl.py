import random
import time
import uuid

from sqlalchemy.exc import SQLAlchemyError

from app.application.dto.product_dto import (
    CachePrewarmResponse,
    DatabaseRouteCheckResponse,
    ProductListQuery,
    ProductResponse,
    ProductSearchQuery,
)
from app.application.interfaces.product_query_service import ProductQueryService
from app.core.config import settings
from app.core.exceptions.business_exception import BusinessException
from app.domain.repositories.product_repository import ProductRepository
from app.domain.services.cache_service import CacheService
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ProductQueryServiceImpl(ProductQueryService):
    def __init__(
        self,
        product_repository: ProductRepository,
        cache_service: CacheService,
    ) -> None:
        self.product_repository = product_repository
        self.cache_service = cache_service

    def list_products(self, query: ProductListQuery) -> list[ProductResponse]:
        cache_key = self._build_list_cache_key(query.page, query.size, query.keyword)
        cached_payload = self.cache_service.get_json(cache_key)
        if isinstance(cached_payload, list):
            logger.info(
                "product list cache hit",
                extra={
                    "event": "product_list_cache_hit",
                    "cache_key": cache_key,
                    "page": query.page,
                    "size": query.size,
                    "keyword": query.keyword,
                },
            )
            return [ProductResponse.model_validate(item) for item in cached_payload]

        return self._rebuild_list_cache(query, cache_key)

    def search_products(self, query: ProductSearchQuery) -> list[ProductResponse]:
        return self.list_products(
            ProductListQuery(page=1, size=query.limit, keyword=query.keyword)
        )

    def get_product_detail(self, product_id: int) -> ProductResponse:
        cache_key = self._build_detail_cache_key(product_id)
        cached_payload = self.cache_service.get_json(cache_key)

        if cached_payload == self.cache_service.null_placeholder:
            raise BusinessException(
                code="PRODUCT_NOT_FOUND",
                message="商品不存在",
                status_code=404,
            )

        if isinstance(cached_payload, dict):
            logger.info(
                "product detail cache hit",
                extra={
                    "event": "product_detail_cache_hit",
                    "product_id": product_id,
                    "cache_key": cache_key,
                },
            )
            return ProductResponse.model_validate(cached_payload)

        return self._rebuild_detail_cache(product_id, cache_key)

    def prewarm_cache(self) -> CachePrewarmResponse:
        default_query = ProductListQuery(page=1, size=settings.DEFAULT_LIST_PAGE_SIZE)
        default_list_cache_key = self._build_list_cache_key(
            default_query.page,
            default_query.size,
            default_query.keyword,
        )

        try:
            total = self.product_repository.count_products(keyword=None)
            synced_items = 0

            first_page_products = self.product_repository.list_products(
                default_query.page,
                default_query.size,
                None,
            )
            default_list_set = self.cache_service.bulk_set_json(
                [
                    (
                        default_list_cache_key,
                        [self._serialize_product(product) for product in first_page_products],
                        self._ttl_with_jitter(settings.CACHE_LIST_TTL_SECONDS),
                    )
                ]
            )
            if not default_list_set:
                raise BusinessException(
                    code="CACHE_PREWARM_FAILED",
                    message="缓存预热失败，请稍后重试",
                    status_code=503,
                )

            # 分批预热详情缓存，避免一次性把所有数据读入内存造成瞬时峰值。
            for offset in range(0, total, settings.CACHE_PREWARM_BATCH_SIZE):
                batch_page = offset // settings.CACHE_PREWARM_BATCH_SIZE + 1
                products = self.product_repository.list_products(
                    page=batch_page,
                    size=settings.CACHE_PREWARM_BATCH_SIZE,
                    keyword=None,
                )
                if not products:
                    break

                batch_entries: list[tuple[str, object, int]] = []
                for product in products:
                    batch_entries.append(
                        (
                            self._build_detail_cache_key(product.id),
                            self._serialize_product(product),
                            self._ttl_with_jitter(settings.CACHE_DETAIL_TTL_SECONDS),
                        )
                    )
                    synced_items += 1

                if not self.cache_service.bulk_set_json(batch_entries):
                    raise BusinessException(
                        code="CACHE_PREWARM_FAILED",
                        message="缓存预热失败，请稍后重试",
                        status_code=503,
                    )
            logger.info(
                "cache prewarm finished",
                extra={
                    "event": "product_cache_prewarm",
                    "count": synced_items,
                    "cache_key": default_list_cache_key,
                },
            )
            return CachePrewarmResponse(
                status="success",
                synced_items=synced_items,
                default_list_cache_key=default_list_cache_key,
            )
        except SQLAlchemyError as exc:
            logger.error(
                "cache prewarm failed",
                exc_info=exc,
                extra={"event": "product_cache_prewarm_failed"},
            )
            raise BusinessException(
                code="CACHE_PREWARM_FAILED",
                message="缓存预热失败，请稍后重试",
                status_code=503,
            ) from exc

    def get_database_route_diagnostics(self) -> DatabaseRouteCheckResponse:
        try:
            snapshot = self.product_repository.get_database_route_snapshot()
        except SQLAlchemyError as exc:
            logger.error(
                "database route check failed",
                exc_info=exc,
                extra={"event": "db_route_check_failed"},
            )
            raise BusinessException(
                code="DB_ROUTE_CHECK_FAILED",
                message="数据库路由检查失败，请稍后重试",
                status_code=503,
            ) from exc

        logger.info(
            "database route check finished",
            extra={
                "event": "db_route_check",
                "read_database": snapshot.read_database,
                "write_database": snapshot.write_database,
            },
        )
        return DatabaseRouteCheckResponse.from_snapshot(snapshot)

    def _rebuild_list_cache(self, query: ProductListQuery, cache_key: str) -> list[ProductResponse]:
        lock_key = f"{cache_key}:lock"
        token = uuid.uuid4().hex

        if self.cache_service.acquire_lock(lock_key, token, settings.CACHE_LOCK_TTL_SECONDS):
            try:
                products = self._load_products_from_db(query)
                payload = [self._serialize_product(product) for product in products]
                self.cache_service.set_json(
                    cache_key,
                    payload,
                    self._ttl_with_jitter(settings.CACHE_LIST_TTL_SECONDS),
                )
                return [ProductResponse.model_validate(item) for item in payload]
            finally:
                self.cache_service.release_lock(lock_key, token)

        cached_payload = self._retry_cache_read(cache_key)
        if isinstance(cached_payload, list):
            return [ProductResponse.model_validate(item) for item in cached_payload]

        products = self._load_products_from_db(query)
        return [ProductResponse.from_entity(product) for product in products]

    def _rebuild_detail_cache(self, product_id: int, cache_key: str) -> ProductResponse:
        lock_key = f"{cache_key}:lock"
        token = uuid.uuid4().hex

        if self.cache_service.acquire_lock(lock_key, token, settings.CACHE_LOCK_TTL_SECONDS):
            try:
                product = self._load_product_from_db(product_id)
                if product is None:
                    self.cache_service.set_placeholder(cache_key, settings.CACHE_NULL_TTL_SECONDS)
                    raise BusinessException(
                        code="PRODUCT_NOT_FOUND",
                        message="商品不存在",
                        status_code=404,
                    )

                payload = self._serialize_product(product)
                self.cache_service.set_json(
                    cache_key,
                    payload,
                    self._ttl_with_jitter(settings.CACHE_DETAIL_TTL_SECONDS),
                )
                return ProductResponse.model_validate(payload)
            finally:
                self.cache_service.release_lock(lock_key, token)

        cached_payload = self._retry_cache_read(cache_key)
        if cached_payload == self.cache_service.null_placeholder:
            raise BusinessException(
                code="PRODUCT_NOT_FOUND",
                message="商品不存在",
                status_code=404,
            )
        if isinstance(cached_payload, dict):
            return ProductResponse.model_validate(cached_payload)

        product = self._load_product_from_db(product_id)
        if product is None:
            raise BusinessException(
                code="PRODUCT_NOT_FOUND",
                message="商品不存在",
                status_code=404,
            )
        return ProductResponse.from_entity(product)

    def _retry_cache_read(self, cache_key: str) -> object | None:
        for attempt in range(settings.CACHE_REBUILD_RETRY_TIMES):
            time.sleep(settings.CACHE_REBUILD_RETRY_INTERVAL_MS / 1000 * (attempt + 1))
            cached_payload = self.cache_service.get_json(cache_key)
            if cached_payload is not None:
                return cached_payload
        return None

    def _load_products_from_db(self, query: ProductListQuery):
        try:
            products = self.product_repository.list_products(query.page, query.size, query.keyword)
            logger.info(
                "product list loaded from database",
                extra={
                    "event": "product_list_db_read",
                    "page": query.page,
                    "size": query.size,
                    "keyword": query.keyword,
                    "count": len(products),
                },
            )
            return products
        except SQLAlchemyError as exc:
            logger.error(
                "product list db read failed",
                exc_info=exc,
                extra={"event": "product_list_db_read_failed"},
            )
            raise BusinessException(
                code="PRODUCT_LIST_READ_FAILED",
                message="商品列表读取失败，请稍后重试",
                status_code=503,
            ) from exc

    def _load_product_from_db(self, product_id: int):
        try:
            product = self.product_repository.get_by_id(product_id)
            logger.info(
                "product detail loaded from database",
                extra={
                    "event": "product_detail_db_read",
                    "product_id": product_id,
                    "outcome": "hit" if product else "miss",
                },
            )
            return product
        except SQLAlchemyError as exc:
            logger.error(
                "product detail db read failed",
                exc_info=exc,
                extra={"event": "product_detail_db_read_failed", "product_id": product_id},
            )
            raise BusinessException(
                code="PRODUCT_DETAIL_READ_FAILED",
                message="商品详情读取失败，请稍后重试",
                status_code=503,
            ) from exc

    def _serialize_product(self, product) -> dict[str, object]:
        return ProductResponse.from_entity(product).model_dump(mode="json")

    def _build_list_cache_key(self, page: int, size: int, keyword: str | None) -> str:
        return f"{settings.CACHE_KEY_PREFIX}:list:page:{page}:size:{size}:keyword:{keyword or '*'}"

    def _build_detail_cache_key(self, product_id: int) -> str:
        return f"{settings.CACHE_KEY_PREFIX}:detail:{product_id}"

    def _ttl_with_jitter(self, base_ttl: int) -> int:
        # TTL 抖动用于打散热点 key 的失效时间，缓解缓存雪崩。
        return base_ttl + random.randint(0, settings.CACHE_TTL_JITTER_SECONDS)
