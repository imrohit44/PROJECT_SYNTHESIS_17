from functools import lru_cache

from backend.app.application.banking import BankApplicationService
from backend.app.core.config import get_settings
from backend.app.infrastructure.persistence.database import create_session_factory


@lru_cache
def get_bank() -> BankApplicationService:
    """Return the process-wide persistence-backed application service."""

    settings = get_settings()
    return BankApplicationService(create_session_factory(settings.database_url))
