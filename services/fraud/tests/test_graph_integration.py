"""Phase 13 Neo4j integration tests.

These require a reachable Neo4j at NEO4J_URI (default bolt://localhost:7687).
They skip automatically when Neo4j is unavailable so the rest of the suite
never depends on the graph database.

Projection tests use dedicated phase13-test ids and clean up after themselves
so real graph data is untouched.
"""

import os
import time
import uuid

import pytest

from graph.client import GraphClient, GraphSettings
from graph.repository import GraphRepository
from graph.risk import GraphRiskAnalyzer, score_signals

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "pybank_neo4j_password")


def _neo4j_available() -> bool:
    probe = GraphClient(GraphSettings(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD))
    try:
        probe.connect()
        return probe.is_available()
    except Exception:
        return False
    finally:
        probe.close()


pytestmark = pytest.mark.skipif(
    not _neo4j_available(), reason="Neo4j is not reachable; integration tests skipped"
)


@pytest.fixture()
def client():
    graph_client = GraphClient(GraphSettings(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD))
    graph_client.connect()
    yield graph_client
    graph_client.close()


@pytest.fixture()
def repo(client):
    return GraphRepository(client)


def _project(repo, txn, src, dst):
    repo.project_transfer(
        source_account_id=src,
        destination_account_id=dst,
        source_customer_id="phase13-cust-a",
        destination_customer_id="phase13-cust-b",
        transaction_id=txn,
        amount="100.00",
        created_ts=float(time.time()),
    )


def test_constraints_exist(client):
    client.ensure_schema()
    rows = client.execute_read("SHOW CONSTRAINTS YIELD name RETURN name")
    names = {str(row["name"]) for row in rows}
    assert any("customer_id_unique" in n for n in names)
    assert any("account_id_unique" in n for n in names)
    assert any("transaction_id_unique" in n for n in names)


def test_projection_is_idempotent(client, repo):
    client.ensure_schema()
    run = uuid.uuid4()
    txn, src, dst = f"phase13-t-{run}", f"phase13-a-{run}", f"phase13-b-{run}"
    try:
        _project(repo, txn, src, dst)
        _project(repo, txn, src, dst)
        rows = client.execute_read(
            "MATCH (t:Transaction {transaction_id: $txn}) RETURN count(t) AS c",
            txn=txn,
        )
        assert rows[0]["c"] == 1
        rels = client.execute_read(
            "MATCH (:Account {account_id: $src})-[r:SENT]->(:Transaction) "
            "RETURN count(r) AS c",
            src=src,
        )
        assert rels[0]["c"] == 1
    finally:
        client.execute_write(
            "MATCH (n) WHERE n.transaction_id = $txn "
            "OR n.account_id IN [$src, $dst] DETACH DELETE n",
            txn=txn,
            src=src,
            dst=dst,
        )


def test_shared_beneficiary_query(client, repo):
    client.ensure_schema()
    run = uuid.uuid4()
    dst = f"phase13-shared-{run}"
    try:
        for i in range(2):
            _project(
                repo, f"phase13-shared-t-{run}-{i}", f"phase13-shared-s-{run}-{i}", dst
            )
        findings = repo.analyze(f"phase13-shared-s-{run}-0", dst, 24 * 3600)
        assert findings.shared_beneficiary_sources == 2
        score, signals = score_signals(findings)
        assert signals == ["SHARED_BENEFICIARY"]
        assert score == pytest.approx(0.4)
    finally:
        client.execute_write(
            "MATCH (n) WHERE n.transaction_id STARTS WITH $prefix "
            "OR n.account_id STARTS WITH $prefix DETACH DELETE n",
            prefix="phase13-shared-",
        )


def test_two_hop_query(client, repo):
    client.ensure_schema()
    run = uuid.uuid4()
    a, b, c = f"phase13-ch-a-{run}", f"phase13-ch-b-{run}", f"phase13-ch-c-{run}"
    try:
        _project(repo, f"phase13-ch-t1-{run}", a, b)
        _project(repo, f"phase13-ch-t2-{run}", b, c)
        assert repo.onward_destinations(b, 24 * 3600) == 1
        findings = repo.analyze(a, b, 24 * 3600)
        score, signals = score_signals(findings)
        assert "MULTI_HOP_CONNECTION" in signals
        assert score == pytest.approx(0.3)
    finally:
        client.execute_write(
            "MATCH (n) WHERE n.transaction_id STARTS WITH $prefix "
            "OR n.account_id STARTS WITH $prefix DETACH DELETE n",
            prefix="phase13-ch-",
        )


def test_recent_counterparty_count(client, repo):
    client.ensure_schema()
    run = uuid.uuid4()
    a = f"phase13-cc-a-{run}"
    try:
        for i in range(6):
            _project(repo, f"phase13-cc-t-{run}-{i}", a, f"phase13-cc-d-{run}-{i}")
        findings = repo.analyze(a, f"phase13-cc-d-{run}-0", 24 * 3600)
        assert findings.recent_counterparties >= 6
        score, signals = score_signals(findings)
        assert "HIGH_RELATIONSHIP_COUNT" in signals
    finally:
        client.execute_write(
            "MATCH (n) WHERE n.transaction_id STARTS WITH $prefix "
            "OR n.account_id STARTS WITH $prefix DETACH DELETE n",
            prefix=f"phase13-cc-{run}",
        )


def test_analyzer_project_and_analyze_roundtrip(client):
    analyzer = GraphRiskAnalyzer(client, lookback_hours=24)
    run = uuid.uuid4()
    try:
        analysis = analyzer.project_and_analyze(
            source_account_id=f"phase13-rd-a-{run}",
            destination_account_id=f"phase13-rd-b-{run}",
            source_customer_id="phase13-cust-a",
            destination_customer_id="phase13-cust-b",
            transaction_id=f"phase13-rd-t-{run}",
            amount="50.00",
            created_ts=float(time.time()),
        )
        assert 0.0 <= analysis.graph_score <= 1.0
    finally:
        client.execute_write(
            "MATCH (n) WHERE n.transaction_id STARTS WITH $prefix "
            "OR n.account_id STARTS WITH $prefix DETACH DELETE n",
            prefix=f"phase13-rd-{run}",
        )
