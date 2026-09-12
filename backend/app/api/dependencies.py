from functools import lru_cache

from backend.app.domain.entities.bank import Bank


@lru_cache
def get_bank() -> Bank:
    """Return the process-local bank until persistent storage exists."""

    return Bank("PyBank")
