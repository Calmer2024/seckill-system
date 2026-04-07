from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.entities.database_route import DatabaseRouteSnapshot
from app.domain.entities.product import ProductEntity


class ProductListQuery(BaseModel):
    page: int = Field(default=1, ge=1, le=10_000)
    size: int = Field(default=20, ge=1, le=100)
    keyword: str | None = Field(default=None, max_length=50)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ProductSearchQuery(BaseModel):
    keyword: str = Field(min_length=1, max_length=50)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("keyword cannot be blank")
        return normalized


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(ge=0)
    stock: int = Field(ge=0)

    @classmethod
    def from_entity(cls, entity: ProductEntity) -> "ProductResponse":
        return cls(
            id=entity.id,
            name=entity.name,
            price=entity.price,
            stock=entity.stock,
        )


class CachePrewarmResponse(BaseModel):
    status: str
    synced_items: int = Field(ge=0)
    default_list_cache_key: str


class DatabaseRouteCheckResponse(BaseModel):
    read_role: str
    write_role: str
    replica_enabled: bool
    read_database: str | None = None
    write_database: str | None = None
    read_product_count: int = Field(ge=0)
    write_product_count: int = Field(ge=0)

    @classmethod
    def from_snapshot(cls, snapshot: DatabaseRouteSnapshot) -> "DatabaseRouteCheckResponse":
        return cls(
            read_role=snapshot.read_role,
            write_role=snapshot.write_role,
            replica_enabled=snapshot.replica_enabled,
            read_database=snapshot.read_database,
            write_database=snapshot.write_database,
            read_product_count=snapshot.read_product_count,
            write_product_count=snapshot.write_product_count,
        )
