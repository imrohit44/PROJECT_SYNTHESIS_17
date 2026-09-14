from __future__ import annotations

import json
import logging
from typing import Any, Protocol, cast

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class Cache(Protocol):
    def get_json(self, key: str) -> Any | None: ...

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None: ...

    def delete(self, *keys: str) -> None: ...


class NullCache:
    def get_json(self, key: str) -> Any | None:
        return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        return None

    def delete(self, *keys: str) -> None:
        return None


class RedisJsonCache:
    def __init__(self, client: Redis, key_prefix: str = "pybank") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def get_json(self, key: str) -> Any | None:
        namespaced = self._name(key)
        try:
            value = self._client.get(namespaced)
        except RedisError:
            logger.warning("cache unavailable during get", extra={"cache_key": key})
            return None
        if value is None:
            logger.debug("cache miss", extra={"cache_key": key})
            return None
        logger.debug("cache hit", extra={"cache_key": key})
        return json.loads(cast(str, value))

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            self._client.setex(self._name(key), ttl_seconds, json.dumps(value))
        except (RedisError, TypeError):
            logger.warning("cache set failed", extra={"cache_key": key})

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            self._client.delete(*(self._name(key) for key in keys))
            logger.debug("cache invalidated", extra={"cache_keys": list(keys)})
        except RedisError:
            logger.warning("cache invalidation failed")

    def _name(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"


def create_cache(redis_url: str | None, enabled: bool = True) -> Cache:
    if not enabled or not redis_url:
        return NullCache()
    return RedisJsonCache(Redis.from_url(redis_url, decode_responses=True))
