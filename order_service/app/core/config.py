from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Order Service"

    ORDER_DATABASE_URL: str = (
        "mysql+pymysql://root:418124@shardingsphere-proxy:3307/order_db?charset=utf8mb4"
    )
    PRODUCT_DATABASE_URL: str = (
        "mysql+pymysql://root:418124@mysql-primary:3306/seckill_db?charset=utf8mb4"
    )
    INVENTORY_SERVICE_URL: str = "http://inventory_service:8000"
    INVENTORY_SERVICE_TIMEOUT_SECONDS: float = 3.0

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

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_ORDER_CREATED_TOPIC: str = "seckill-order-created-topic"
    KAFKA_INVENTORY_RESULT_TOPIC: str = "seckill-inventory-result-topic"
    KAFKA_PAYMENT_TOPIC: str = "seckill-payment-topic"
    KAFKA_OUTBOX_GROUP_ID: str = "seckill-order-outbox"
    KAFKA_INVENTORY_RESULT_GROUP_ID: str = "seckill-order-inventory-result"
    KAFKA_PAYMENT_GROUP_ID: str = "seckill-order-payment"
    OUTBOX_PUBLISH_BATCH_SIZE: int = 50
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    ENABLE_KAFKA_ASYNC: bool = True
    ENABLE_ORDER_OUTBOX: bool = True

    JWT_SECRET_KEY: str = "fallback_secret_key_for_dev"
    JWT_ALGORITHM: str = "HS256"

    SNOWFLAKE_EPOCH_MILLISECONDS: int = 1704067200000
    SNOWFLAKE_DATACENTER_ID: int = 1
    SNOWFLAKE_WORKER_ID: int = 1

    LOG_LEVEL: str = "INFO"


settings = Settings()
