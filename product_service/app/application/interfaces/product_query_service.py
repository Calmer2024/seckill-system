from abc import ABC, abstractmethod

from app.application.dto.product_dto import (
    CachePrewarmResponse,
    DatabaseRouteCheckResponse,
    ProductListQuery,
    ProductResponse,
    ProductSearchQuery,
)


class ProductQueryService(ABC):
    @abstractmethod
    def list_products(self, query: ProductListQuery) -> list[ProductResponse]:
        raise NotImplementedError

    @abstractmethod
    def search_products(self, query: ProductSearchQuery) -> list[ProductResponse]:
        raise NotImplementedError

    @abstractmethod
    def get_product_detail(self, product_id: int) -> ProductResponse:
        raise NotImplementedError

    @abstractmethod
    def prewarm_cache(self) -> CachePrewarmResponse:
        raise NotImplementedError

    @abstractmethod
    def get_database_route_diagnostics(self) -> DatabaseRouteCheckResponse:
        raise NotImplementedError
