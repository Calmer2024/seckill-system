# 提取硬编码配置，支持读写分离和缓存防护参数通过环境变量动态调整。
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Product Service"

    DATABASE_URL: str = "mysql+pymysql://root:418124@mysql-primary:3306/seckill_db"
    READ_DATABASE_URL: str | None = None
    WRITE_DATABASE_ROLE_NAME: str = "primary"
    READ_DATABASE_ROLE_NAME: str = "replica"
    ENABLE_READ_REPLICA_FALLBACK: bool = True

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

    CACHE_KEY_PREFIX: str = "product"
    CACHE_NULL_TTL_SECONDS: int = 60
    CACHE_LIST_TTL_SECONDS: int = 180
    CACHE_DETAIL_TTL_SECONDS: int = 900
    CACHE_TTL_JITTER_SECONDS: int = 120
    CACHE_LOCK_TTL_SECONDS: int = 5
    CACHE_REBUILD_RETRY_TIMES: int = 3
    CACHE_REBUILD_RETRY_INTERVAL_MS: int = 60
    CACHE_PREWARM_BATCH_SIZE: int = 200
    DEFAULT_LIST_PAGE_SIZE: int = 20

    LOG_LEVEL: str = "INFO"

    @property
    def effective_read_database_url(self) -> str:
        return self.READ_DATABASE_URL or self.DATABASE_URL

    @property
    def read_replica_enabled(self) -> bool:
        return bool(self.READ_DATABASE_URL and self.READ_DATABASE_URL != self.DATABASE_URL)


settings = Settings()
