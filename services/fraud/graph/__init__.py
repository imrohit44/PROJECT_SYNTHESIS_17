"""Graph-based fraud relationship analysis (Phase 13).

Neo4j is an analytical READ MODEL — a projection of existing Kafka events.
It is never the source of truth for balances, accounts or assessments.
"""

from .client import GraphClient, GraphSettings
from .repository import GraphRepository
from .risk import (
    GRAPH_VERSION,
    GraphAnalysis,
    GraphRiskAnalyzer,
    score_signals,
)

__all__ = [
    "GRAPH_VERSION",
    "GraphAnalysis",
    "GraphClient",
    "GraphRepository",
    "GraphRiskAnalyzer",
    "GraphSettings",
    "score_signals",
]
