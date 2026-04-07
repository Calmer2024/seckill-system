from abc import ABC, abstractmethod


class CacheService(ABC):
    null_placeholder = "__NULL__"

    @abstractmethod
    def get_json(self, key: str) -> object | None:
        raise NotImplementedError

    @abstractmethod
    def set_json(self, key: str, payload: object, ttl_seconds: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_placeholder(self, key: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def acquire_lock(self, key: str, token: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def release_lock(self, key: str, token: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def bulk_set_json(self, entries: list[tuple[str, object, int]]) -> bool:
        raise NotImplementedError
