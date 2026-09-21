"""Phase 13 unit tests: graph risk calculation, boundaries, fallback.

These tests do NOT require a running Neo4j instance; the graph adapter is
mocked. Neo4j-dependent integration tests live in test_graph_integration.py
and skip automatically when Neo4j is unreachable.
"""

import pytest

from graph.repository import GraphFindings
from graph.risk import (
    GRAPH_VERSION,
    GraphAnalysis,
    GraphRiskAnalyzer,
    score_signals,
)


class StubAnalyzer(GraphRiskAnalyzer):
    """Analyzer with fixed configuration for deterministic unit tests."""

    def __init__(self) -> None:
        pass  # skip Neo4j-dependent parent init

    @property
    def graph_version(self) -> str:
        return GRAPH_VERSION

    def adjustment_for(self, graph_score: float) -> float:
        return min(0.15, 0.25 * graph_score)


def test_no_suspicious_relationships_scores_zero():
    findings = GraphFindings(
        shared_beneficiary_sources=1,
        onward_destinations=0,
        recent_counterparties=2,
    )
    score, signals = score_signals(findings)
    assert score == 0.0
    assert signals == []


def test_shared_beneficiary_signal_fires_at_two_sources():
    findings = GraphFindings(
        shared_beneficiary_sources=2, onward_destinations=0, recent_counterparties=2
    )
    score, signals = score_signals(findings)
    assert score == pytest.approx(0.4)
    assert signals == ["SHARED_BENEFICIARY"]


def test_shared_beneficiary_scales_and_caps():
    three = score_signals(GraphFindings(3, 0, 0))
    ten = score_signals(GraphFindings(10, 0, 0))
    assert three[0] == pytest.approx(0.5)
    assert ten[0] == pytest.approx(0.6)  # capped


def test_multi_hop_and_relationship_count_signals():
    score, signals = score_signals(GraphFindings(0, 1, 0))
    assert score == pytest.approx(0.3)
    assert signals == ["MULTI_HOP_CONNECTION"]

    score, signals = score_signals(GraphFindings(0, 0, 5))
    assert score == pytest.approx(0.2)
    assert signals == ["HIGH_RELATIONSHIP_COUNT"]


def test_combined_signals_and_score_boundaries():
    score, signals = score_signals(GraphFindings(5, 2, 7))
    assert score == pytest.approx(min(1.0, 0.6 + 0.3 + 0.2))
    assert set(signals) == {
        "SHARED_BENEFICIARY",
        "MULTI_HOP_CONNECTION",
        "HIGH_RELATIONSHIP_COUNT",
    }
    assert 0.0 <= score <= 1.0


def test_graph_version_is_stable():
    assert GRAPH_VERSION == "fraud-graph-v1"


def test_adjustment_is_bounded():
    analyzer = StubAnalyzer()
    assert analyzer.adjustment_for(0.0) == 0.0
    assert analyzer.adjustment_for(0.5) == pytest.approx(0.125)
    # 0.25 * 1.0 would be 0.25 but is capped at GRAPH_MAX_ADJUSTMENT.
    assert analyzer.adjustment_for(1.0) == pytest.approx(0.15)


def test_analyzer_reads_env_config(monkeypatch):
    monkeypatch.setenv("GRAPH_LOOKBACK_HOURS", "6")
    monkeypatch.setenv("GRAPH_WEIGHT", "0.5")
    monkeypatch.setenv("GRAPH_MAX_ADJUSTMENT", "0.2")
    analyzer = GraphRiskAnalyzer(client=object())  # client unused by config
    assert analyzer.lookback_seconds == 6 * 3600
    assert analyzer.graph_weight == pytest.approx(0.5)
    assert analyzer.max_adjustment == pytest.approx(0.2)


def test_analysis_dataclass_defaults():
    analysis = GraphAnalysis(graph_score=0.4, graph_signals=["SHARED_BENEFICIARY"])
    assert analysis.graph_signals == ["SHARED_BENEFICIARY"]
