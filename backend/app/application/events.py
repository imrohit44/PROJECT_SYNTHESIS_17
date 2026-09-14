from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "payload": {key: json_value(value) for key, value in self.payload.items()},
        }


def account_created_event(
    account_id: str, customer_id: str, account_type: str
) -> EventEnvelope:
    return EventEnvelope(
        event_type="account.created",
        aggregate_type="account",
        aggregate_id=account_id,
        payload={
            "account_id": account_id,
            "customer_id": customer_id,
            "account_type": account_type,
        },
    )


def deposit_completed_event(
    account_id: str, customer_id: str, amount: Decimal, transaction_id: str
) -> EventEnvelope:
    return EventEnvelope(
        event_type="deposit.completed",
        aggregate_type="account",
        aggregate_id=account_id,
        payload={
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": amount,
            "transaction_id": transaction_id,
        },
    )


def withdrawal_completed_event(
    account_id: str, customer_id: str, amount: Decimal, transaction_id: str
) -> EventEnvelope:
    return EventEnvelope(
        event_type="withdrawal.completed",
        aggregate_type="account",
        aggregate_id=account_id,
        payload={
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": amount,
            "transaction_id": transaction_id,
        },
    )


def transfer_completed_event(
    source_account_id: str,
    destination_account_id: str,
    source_customer_id: str,
    destination_customer_id: str,
    amount: Decimal,
    source_transaction_id: str,
    destination_transaction_id: str,
) -> EventEnvelope:
    return EventEnvelope(
        event_type="transfer.completed",
        aggregate_type="transfer",
        aggregate_id=source_transaction_id,
        payload={
            "source_account_id": source_account_id,
            "destination_account_id": destination_account_id,
            "source_customer_id": source_customer_id,
            "destination_customer_id": destination_customer_id,
            "amount": amount,
            "source_transaction_id": source_transaction_id,
            "destination_transaction_id": destination_transaction_id,
        },
    )
