from functools import lru_cache

from backend.app.application.auth import AuthApplicationService
from backend.app.application.banking import BankApplicationService
from backend.app.core.config import get_settings
from backend.app.infrastructure.cache import Cache, create_cache
from backend.app.infrastructure.persistence.database import create_session_factory
from backend.app.security.passwords import PasswordService
from backend.app.security.rate_limit import LoginRateLimiter
from backend.app.security.tokens import TokenService


@lru_cache
def get_bank() -> BankApplicationService:
    """Return the process-wide persistence-backed application service."""

    settings = get_settings()
    return BankApplicationService(create_session_factory(settings.database_url))


@lru_cache
def get_auth() -> AuthApplicationService:
    settings = get_settings()
    return AuthApplicationService(
        create_session_factory(settings.database_url),
        PasswordService(),
        TokenService(
            settings.jwt_secret,
            settings.jwt_algorithm,
            settings.access_token_minutes,
            settings.refresh_token_days,
        ),
    )


@lru_cache
def get_login_limiter() -> LoginRateLimiter:
    settings = get_settings()
    return LoginRateLimiter(
        settings.login_rate_limit,
        settings.login_rate_window_seconds,
        redis_url=settings.redis_url,
    )


@lru_cache
def get_cache() -> Cache:
    settings = get_settings()
    return create_cache(settings.redis_url, settings.cache_enabled)
