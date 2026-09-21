"""Phase 13 fallback tests: Neo4j unavailable must not block assessments."""

from graph.risk import GraphRiskAnalyzer


class ExplodingAnalyzer(GraphRiskAnalyzer):
    """Analyzer whose Neo4j dependency always fails."""

    def __init__(self) -> None:
        pass

    @property
    def graph_version(self) -> str:
        return "fraud-graph-v1"

    def adjustment_for(self, graph_score: float) -> float:
        return 0.0

    def project_and_analyze(self, **_: object) -> object:
        raise ConnectionError("neo4j down")


def test_unreachable_client_reports_unavailable():
    from graph.client import GraphClient, GraphSettings

    client = GraphClient(GraphSettings("bolt://localhost:1", "user", "pass"))
    try:
        assert client.is_available() is False
    finally:
        client.close()


def test_analyzer_availability_is_false_on_failure():
    analyzer = ExplodingAnalyzer()
    assert analyzer.is_available() is False
