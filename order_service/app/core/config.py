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
    KAFKA_ORDER_TOPIC: str = "seckill-order-topic"
    KAFKA_CONSUMER_GROUP_ID: str = "seckill-order-worker"

    JWT_SECRET_KEY: str = "fallback_secret_key_for_dev"
    JWT_ALGORITHM: str = "HS256"

    SNOWFLAKE_EPOCH_MILLISECONDS: int = 1704067200000
    SNOWFLAKE_DATACENTER_ID: int = 1
    SNOWFLAKE_WORKER_ID: int = 1

    LOG_LEVEL: str = "INFO"


settings = Settings()
