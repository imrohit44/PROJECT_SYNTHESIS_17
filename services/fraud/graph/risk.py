"""Deterministic graph-risk translation (no machine learning).

Findings from the graph are mapped to a bounded, transparent score:

    SHARED_BENEFICIARY   >= 2 distinct recent sources -> 0.4 (+0.1 per extra
                          source beyond 2, capped at 0.6)
    MULTI_HOP_CONNECTION destination sent money onward -> 0.3
    HIGH_RELATIONSHIP_COUNT >= 5 recent counterparties -> 0.2

    graph_score = min(1.0, sum of signal contributions)

These are educational heuristics, not proven fraud indicators.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .client import GraphClient
from .repository import GraphFindings, GraphRepository

GRAPH_VERSION = "fraud-graph-v1"

SHARED_BENEFICIARY_BASE = 0.4
SHARED_BENEFICIARY_STEP = 0.1
SHARED_BENEFICIARY_CAP = 0.6
MULTI_HOP_SCORE = 0.3
HIGH_RELATIONSHIP_SCORE = 0.2
HIGH_RELATIONSHIP_THRESHOLD = 5


def score_signals(findings: GraphFindings) -> tuple[float, list[str]]:
    """Deterministically map graph findings to (score, signal names)."""
    score = 0.0
    signals: list[str] = []

    if findings.shared_beneficiary_sources >= 2:
        bonus = min(
            SHARED_BENEFICIARY_CAP,
            SHARED_BENEFICIARY_BASE
            + (findings.shared_beneficiary_sources - 2) * SHARED_BENEFICIARY_STEP,
        )
        score += bonus
        signals.append("SHARED_BENEFICIARY")

    if findings.onward_destinations > 0:
        score += MULTI_HOP_SCORE
        signals.append("MULTI_HOP_CONNECTION")

    if findings.recent_counterparties >= HIGH_RELATIONSHIP_THRESHOLD:
        score += HIGH_RELATIONSHIP_SCORE
        signals.append("HIGH_RELATIONSHIP_COUNT")

    return min(score, 1.0), signals


@dataclass(frozen=True)
class GraphAnalysis:
    graph_score: float
    graph_signals: list[str] = field(default_factory=list)


class GraphRiskAnalyzer:
    """Facade the consumer depends on: project + analyze + score.

    Neo4j failures are converted into a neutral analysis (score 0.0) by the
    CALLER; this class surfaces exceptions so failures stay observable.
    """

    def __init__(
        self,
        client: GraphClient,
        lookback_hours: int | None = None,
        graph_weight: float | None = None,
        max_adjustment: float | None = None,
    ) -> None:
        self._client = client
        self._repository = GraphRepository(client)
        self._lookback_hours = int(
            lookback_hours
            if lookback_hours is not None
            else os.getenv("GRAPH_LOOKBACK_HOURS", "24")
        )
        self.graph_weight = float(
            graph_weight
            if graph_weight is not None
            else os.getenv("GRAPH_WEIGHT", "0.25")
        )
        self.max_adjustment = float(
            max_adjustment
            if max_adjustment is not None
            else os.getenv("GRAPH_MAX_ADJUSTMENT", "0.15")
        )

    @property
    def graph_version(self) -> str:
        return GRAPH_VERSION

    @property
    def lookback_seconds(self) -> int:
        return self._lookback_hours * 3600

    def adjustment_for(self, graph_score: float) -> float:
        """Configurable bounded contribution of the graph to the final score."""
        return min(self.max_adjustment, self.graph_weight * graph_score)

    def is_available(self) -> bool:
        try:
            return self._client.is_available()
        except Exception:
            return False

    def project(
        self,
        source_account_id: str,
        destination_account_id: str,
        source_customer_id: str,
        destination_customer_id: str,
        transaction_id: str,
        amount: str,
        created_ts: float,
    ) -> None:
        """Idempotently project one transfer into the graph."""
        self._repository.project_transfer(
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            source_customer_id=source_customer_id,
            destination_customer_id=destination_customer_id,
            transaction_id=transaction_id,
            amount=amount,
            created_ts=created_ts,
        )

    def analyze_transfer(
        self, source_account_id: str, destination_account_id: str
    ) -> GraphAnalysis:
        """Run the bounded relationship queries for one transfer."""
        findings = self._repository.analyze(
            source_account_id,
            destination_account_id,
            self.lookback_seconds,
        )
        score, signals = score_signals(findings)
        return GraphAnalysis(graph_score=score, graph_signals=signals)

    def project_and_analyze(
        self,
        source_account_id: str,
        destination_account_id: str,
        source_customer_id: str,
        destination_customer_id: str,
        transaction_id: str,
        amount: str,
        created_ts: float,
    ) -> GraphAnalysis:
        """Project then analyze. Raises on Neo4j failure so the caller can
        log + metric it and fall back to a neutral graph contribution."""
        self.project(
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            source_customer_id=source_customer_id,
            destination_customer_id=destination_customer_id,
            transaction_id=transaction_id,
            amount=amount,
            created_ts=created_ts,
        )
        return self.analyze_transfer(source_account_id, destination_account_id)
