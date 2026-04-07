from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Inventory Service"

    INVENTORY_DATABASE_URL: str = (
        "mysql+pymysql://root:418124@mysql-primary:3306/inventory_db?charset=utf8mb4"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_CONNECT_TIMEOUT_SECONDS: int = 3
    DB_READ_TIMEOUT_SECONDS: int = 3
    DB_WRITE_TIMEOUT_SECONDS: int = 3

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    REDIS_MAX_CONNECTIONS: int = 256
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: int = 1
    REDIS_SOCKET_TIMEOUT_SECONDS: int = 1
    SECKILL_RESERVATION_TTL_SECONDS: int = 900
    ORDER_STATUS_TTL_SECONDS: int = 1800

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_ORDER_CREATED_TOPIC: str = "seckill-order-created-topic"
    KAFKA_INVENTORY_RESULT_TOPIC: str = "seckill-inventory-result-topic"
    KAFKA_ORDER_CREATED_GROUP_ID: str = "seckill-inventory-order-created"
    OUTBOX_PUBLISH_BATCH_SIZE: int = 50
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0

    LOG_LEVEL: str = "INFO"


settings = Settings()
