from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import cast

from redis import Redis
from redis.exceptions import RedisError


class LoginRateLimiter:
    """Login limiter using Redis when available, with local fallback."""

    def __init__(
        self, max_attempts: int, window_seconds: int, redis_url: str | None = None
    ) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._redis = (
            Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        )

    def allow(self, key: str) -> bool:
        if self._redis is not None:
            try:
                redis_key = f"pybank:rate-limit:login:{key}"
                count = cast(int, self._redis.incr(redis_key))
                if count == 1:
                    self._redis.expire(redis_key, self._window_seconds)
                return int(count) <= self._max_attempts
            except RedisError:
                return True

        now = monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] >= self._window_seconds:
                attempts.popleft()
            if len(attempts) >= self._max_attempts:
                return False
            attempts.append(now)
            return True
