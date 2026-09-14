from redis.exceptions import RedisError

from backend.app.security.rate_limit import LoginRateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds


class FailingRedis:
    def incr(self, key: str) -> int:
        raise RedisError("redis unavailable")


def test_redis_backed_rate_limit_shares_state() -> None:
    shared = FakeRedis()
    first = LoginRateLimiter(2, 60)
    second = LoginRateLimiter(2, 60)
    first._redis = shared
    second._redis = shared

    assert first.allow("alice@example.com")
    assert second.allow("alice@example.com")
    assert not first.allow("alice@example.com")
    assert shared.expirations["pybank:rate-limit:login:alice@example.com"] == 60


def test_redis_rate_limit_fails_open_for_availability() -> None:
    limiter = LoginRateLimiter(1, 60)
    limiter._redis = FailingRedis()

    assert limiter.allow("alice@example.com")
