from abc import ABC, abstractmethod

from app.domain.entities.database_route import DatabaseRouteSnapshot
from app.domain.entities.product import ProductEntity


class ProductRepository(ABC):
    @abstractmethod
    def get_by_id(self, product_id: int) -> ProductEntity | None:
        raise NotImplementedError

    @abstractmethod
    def list_products(self, page: int, size: int, keyword: str | None) -> list[ProductEntity]:
        raise NotImplementedError

    @abstractmethod
    def count_products(self, keyword: str | None) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_database_route_snapshot(self) -> DatabaseRouteSnapshot:
        raise NotImplementedError
