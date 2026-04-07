import json

import redis

from app.domain.services.cache_service import CacheService
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

LOCK_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class RedisCacheService(CacheService):
    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis_client = redis_client
        self._release_lock_script = self.redis_client.register_script(LOCK_RELEASE_SCRIPT)

    def get_json(self, key: str) -> object | None:
        try:
            raw_value = self.redis_client.get(key)
            if raw_value is None:
                return None
            if raw_value == self.null_placeholder:
                return self.null_placeholder
            return json.loads(raw_value)
        except (redis.RedisError, json.JSONDecodeError) as exc:
            logger.error(
                "redis get failed",
                exc_info=exc,
                extra={"event": "redis_get_failed", "cache_key": key},
            )
            return None

    def set_json(self, key: str, payload: object, ttl_seconds: int) -> bool:
        try:
            self.redis_client.set(name=key, value=json.dumps(payload), ex=ttl_seconds)
            return True
        except redis.RedisError as exc:
            logger.error(
                "redis set failed",
                exc_info=exc,
                extra={"event": "redis_set_failed", "cache_key": key},
            )
            return False

    def set_placeholder(self, key: str, ttl_seconds: int) -> bool:
        try:
            self.redis_client.set(name=key, value=self.null_placeholder, ex=ttl_seconds)
            return True
        except redis.RedisError as exc:
            logger.error(
                "redis placeholder set failed",
                exc_info=exc,
                extra={"event": "redis_placeholder_set_failed", "cache_key": key},
            )
            return False

    def acquire_lock(self, key: str, token: str, ttl_seconds: int) -> bool:
        try:
            return bool(self.redis_client.set(name=key, value=token, nx=True, ex=ttl_seconds))
        except redis.RedisError as exc:
            logger.error(
                "redis lock acquire failed",
                exc_info=exc,
                extra={"event": "redis_lock_acquire_failed", "cache_key": key},
            )
            return False

    def release_lock(self, key: str, token: str) -> bool:
        try:
            self._release_lock_script(keys=[key], args=[token])
            return True
        except redis.RedisError as exc:
            logger.error(
                "redis lock release failed",
                exc_info=exc,
                extra={"event": "redis_lock_release_failed", "cache_key": key},
            )
            return False

    def bulk_set_json(self, entries: list[tuple[str, object, int]]) -> bool:
        if not entries:
            return True

        try:
            pipeline = self.redis_client.pipeline()
            for key, payload, ttl_seconds in entries:
                pipeline.set(name=key, value=json.dumps(payload), ex=ttl_seconds)
            pipeline.execute()
            return True
        except redis.RedisError as exc:
            logger.error(
                "redis bulk set failed",
                exc_info=exc,
                extra={"event": "redis_bulk_set_failed", "count": len(entries)},
            )
            return False
