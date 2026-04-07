from collections.abc import Generator

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings


Base = declarative_base()


def _build_engine(database_url: str):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        connect_args={
            "connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
            "read_timeout": settings.DB_READ_TIMEOUT_SECONDS,
            "write_timeout": settings.DB_WRITE_TIMEOUT_SECONDS,
        },
    )


order_engine = _build_engine(settings.ORDER_DATABASE_URL)
product_engine = _build_engine(settings.PRODUCT_DATABASE_URL)

OrderSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=order_engine)
ProductSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=product_engine)


def get_order_db() -> Generator[Session, None, None]:
    db = OrderSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_product_db() -> Generator[Session, None, None]:
    db = ProductSessionLocal()
    try:
        yield db
    finally:
        db.close()


redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,
    max_connections=settings.REDIS_MAX_CONNECTIONS,
    socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
    socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
)
redis_client = redis.Redis(connection_pool=redis_pool)


def get_redis_client() -> redis.Redis:
    return redis_client
