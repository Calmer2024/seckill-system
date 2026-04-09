import json
from decimal import Decimal

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.entities.database_route import DatabaseRouteSnapshot
from app.domain.entities.product import ProductEntity
from app.domain.repositories.product_repository import ProductRepository
from app.infrastructure.logging.logger import get_logger
from app.models.product import Product

logger = get_logger(__name__)


class SqlAlchemyProductRepository(ProductRepository):
    def __init__(self, read_session: Session, write_session: Session) -> None:
        self.read_session = read_session
        self.write_session = write_session

    def get_by_id(self, product_id: int) -> ProductEntity | None:
        statement = select(Product).where(Product.id == product_id)
        product = self._execute_read(statement).scalar_one_or_none()
        return self._to_entity(product) if product else None

    def list_products(self, page: int, size: int, keyword: str | None) -> list[ProductEntity]:
        statement = select(Product)
        if keyword:
            like_pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    Product.name.like(like_pattern),
                    Product.category.like(like_pattern),
                    Product.highlight.like(like_pattern),
                    Product.summary.like(like_pattern),
                    Product.tags.like(like_pattern),
                )
            )

        statement = statement.order_by(Product.id.asc()).offset((page - 1) * size).limit(size)
        products = self._execute_read(statement).scalars().all()
        return [self._to_entity(product) for product in products]

    def count_products(self, keyword: str | None) -> int:
        statement = select(func.count(Product.id))
        if keyword:
            like_pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    Product.name.like(like_pattern),
                    Product.category.like(like_pattern),
                    Product.highlight.like(like_pattern),
                    Product.summary.like(like_pattern),
                    Product.tags.like(like_pattern),
                )
            )
        return int(self._execute_read(statement).scalar_one())

    def get_database_route_snapshot(self) -> DatabaseRouteSnapshot:
        write_database = self.write_session.execute(text("SELECT DATABASE()")).scalar_one_or_none()
        write_count = int(self.write_session.execute(select(func.count(Product.id))).scalar_one())

        read_database = None
        read_count = 0
        try:
            read_database = self.read_session.execute(text("SELECT DATABASE()")).scalar_one_or_none()
            read_count = int(self.read_session.execute(select(func.count(Product.id))).scalar_one())
        except SQLAlchemyError as exc:
            logger.error(
                "read database diagnostics failed, falling back to write database",
                exc_info=exc,
                extra={"event": "read_diagnostics_failed", "db_role": settings.READ_DATABASE_ROLE_NAME},
            )
            if not settings.ENABLE_READ_REPLICA_FALLBACK:
                raise
            read_database = write_database
            read_count = write_count

        return DatabaseRouteSnapshot(
            read_role=settings.READ_DATABASE_ROLE_NAME,
            write_role=settings.WRITE_DATABASE_ROLE_NAME,
            replica_enabled=settings.read_replica_enabled,
            read_database=read_database,
            write_database=write_database,
            read_product_count=read_count,
            write_product_count=write_count,
        )

    def _execute_read(self, statement):
        try:
            return self.read_session.execute(statement)
        except SQLAlchemyError as exc:
            logger.error(
                "read database query failed",
                exc_info=exc,
                extra={"event": "read_query_failed", "db_role": settings.READ_DATABASE_ROLE_NAME},
            )
            if not settings.ENABLE_READ_REPLICA_FALLBACK:
                raise
            logger.info(
                "read database fallback to write database",
                extra={
                    "event": "read_query_fallback",
                    "db_role": settings.WRITE_DATABASE_ROLE_NAME,
                },
            )
            return self.write_session.execute(statement)

    @staticmethod
    def _to_entity(product: Product) -> ProductEntity:
        return ProductEntity(
            id=product.id,
            name=product.name,
            price=Decimal(str(product.price)),
            stock=product.stock,
            category=product.category,
            rating=float(product.rating or 0),
            review_count=int(product.review_count or 0),
            tags=json.loads(product.tags or "[]"),
            summary=product.summary or "",
            highlight=product.highlight or "",
            visual_icon=product.visual_icon or "lucide:package-open",
        )
