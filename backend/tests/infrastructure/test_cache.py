import json

from backend.app.infrastructure.cache import RedisJsonCache


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.deleted: list[str] = []

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)


def test_cache_set_get_ttl_and_delete() -> None:
    redis = FakeRedis()
    cache = RedisJsonCache(redis, key_prefix="test")

    assert cache.get_json("missing") is None

    cache.set_json("account:1", {"balance": "10.00"}, ttl_seconds=60)

    assert redis.ttls["test:account:1"] == 60
    assert json.loads(redis.values["test:account:1"]) == {"balance": "10.00"}
    assert cache.get_json("account:1") == {"balance": "10.00"}

    cache.delete("account:1")

    assert "test:account:1" in redis.deleted
    assert cache.get_json("account:1") is None
