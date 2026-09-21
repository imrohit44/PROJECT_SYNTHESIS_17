"""Graph repository: idempotent projection + bounded relationship queries.

All writes use MERGE on stable business identifiers (customer_id, account_id,
transaction_id), so replaying the same Kafka event can never create duplicate
nodes or relationships. All reads return small, bounded aggregates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import queries
from .client import GraphClient


def _count(rows: list[dict[str, Any]], key: str) -> int:
    return int(rows[0][key]) if rows else 0


@dataclass(frozen=True)
class GraphFindings:
    shared_beneficiary_sources: int
    onward_destinations: int
    recent_counterparties: int


class GraphRepository:
    def __init__(self, client: GraphClient) -> None:
        self._client = client

    # --- projection ---------------------------------------------------------

    def project_transfer(
        self,
        source_account_id: str,
        destination_account_id: str,
        source_customer_id: str,
        destination_customer_id: str,
        transaction_id: str,
        amount: str,
        created_ts: float,
    ) -> None:
        """MERGE one transfer's entities/relationships. Idempotent."""
        self._client.ensure_schema()
        self._client.execute_write(
            queries.PROJECT_TRANSFER,
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            source_customer_id=source_customer_id,
            destination_customer_id=destination_customer_id,
            transaction_id=transaction_id,
            amount=amount,
            created_ts=created_ts,
        )

    # --- analysis -----------------------------------------------------------

    def shared_beneficiary_sources(
        self, destination_account_id: str, lookback_seconds: int
    ) -> int:
        rows = self._client.execute_read(
            queries.SHARED_BENEFICIARY,
            destination_account_id=destination_account_id,
            lookback_seconds=lookback_seconds,
        )
        return _count(rows, "source_count")

    def onward_destinations(
        self, destination_account_id: str, lookback_seconds: int
    ) -> int:
        rows = self._client.execute_read(
            queries.TWO_HOP,
            destination_account_id=destination_account_id,
            lookback_seconds=lookback_seconds,
        )
        return _count(rows, "onward_count")

    def recent_counterparties(self, account_id: str, lookback_seconds: int) -> int:
        rows = self._client.execute_read(
            queries.RELATIONSHIP_COUNT,
            account_id=account_id,
            lookback_seconds=lookback_seconds,
        )
        return _count(rows, "counterparty_count")

    def analyze(
        self, account_id: str, destination_account_id: str, lookback_seconds: int
    ) -> GraphFindings:
        return GraphFindings(
            shared_beneficiary_sources=self.shared_beneficiary_sources(
                destination_account_id, lookback_seconds
            ),
            onward_destinations=self.onward_destinations(
                destination_account_id, lookback_seconds
            ),
            recent_counterparties=self.recent_counterparties(
                account_id, lookback_seconds
            ),
        )
