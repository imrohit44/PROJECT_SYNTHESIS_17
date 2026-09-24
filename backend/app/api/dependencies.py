from functools import lru_cache

from backend.app.application.auth import AuthApplicationService
from backend.app.application.banking import BankApplicationService
from backend.app.core.config import get_settings
from backend.app.infrastructure.cache import Cache, create_cache
from backend.app.infrastructure.persistence.database import create_session_factory
from backend.app.llm.client import LLMClient
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
    # Test runs use the process-local limiter so counters cannot leak between
    # tests through Redis. Production behaviour is unchanged.
    redis_url = None if settings.app_env == "test" else settings.redis_url
    return LoginRateLimiter(
        settings.login_rate_limit,
        settings.login_rate_window_seconds,
        redis_url=redis_url,
    )


@lru_cache
def get_cache() -> Cache:
    settings = get_settings()
    return create_cache(settings.redis_url, settings.cache_enabled)


@lru_cache
def get_assistant_limiter() -> LoginRateLimiter:
    """Rate limiter for the read-only banking assistant (Phase 14).

    Mirrors ``get_login_limiter``: tests use the process-local limiter so
    counters cannot leak between tests; production behaviour is unchanged.
    """
    settings = get_settings()
    redis_url = None if settings.app_env == "test" else settings.redis_url
    return LoginRateLimiter(
        settings.assistant_rate_limit,
        settings.assistant_rate_window_seconds,
        redis_url=redis_url,
    )


@lru_cache
def get_llm_client() -> LLMClient:
    """Return the process-wide LLM client.

    The client is created even when unconfigured: calling it then raises
    ``LLMNotConfiguredError``, so the banking API keeps working without any
    LLM configuration and the assistant endpoint reports 503 explicitly.
    """
    settings = get_settings()
    return LLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
    )
