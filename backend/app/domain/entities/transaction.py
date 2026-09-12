from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from backend.app.domain.enums import TransactionStatus, TransactionType


@dataclass(frozen=True, slots=True)
class Transaction:
    """Immutable record of a completed domain operation."""

    transaction_type: TransactionType
    amount: Decimal
    source_account_id: str | None = None
    destination_account_id: str | None = None
    status: TransactionStatus = TransactionStatus.COMPLETED
    transaction_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
