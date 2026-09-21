"""Cypher queries for graph projection and fraud relationship analysis.

Every query is parameterized (never string-interpolated) and bounded. Analysis
queries always restrict lookups to a specific account/transaction id and use
the ``created_ts`` epoch-seconds property with a lookback window instead of
scanning the whole graph.
"""

from __future__ import annotations

# --- Projection (idempotent via MERGE on stable business identifiers) -------

PROJECT_TRANSFER = """
MERGE (src:Account {account_id: $source_account_id})
MERGE (dst:Account {account_id: $destination_account_id})
MERGE (srcC:Customer {customer_id: $source_customer_id})
MERGE (dstC:Customer {customer_id: $destination_customer_id})
MERGE (srcC)-[:OWNS]->(src)
MERGE (dstC)-[:OWNS]->(dst)
MERGE (t:Transaction {transaction_id: $transaction_id})
  ON CREATE SET t.amount = $amount, t.created_ts = $created_ts
MERGE (src)-[:SENT {amount: $amount}]->(t)
MERGE (t)-[:RECEIVED_BY]->(dst)
"""

# --- Analysis ---------------------------------------------------------------

# 1. Shared beneficiary: how many DISTINCT source accounts recently sent to
# the destination of the transaction being assessed?
SHARED_BENEFICIARY = """
MATCH (src:Account)-[:SENT]->(t:Transaction)
      -[:RECEIVED_BY]->(dst:Account {account_id: $destination_account_id})
WHERE t.created_ts > timestamp() / 1000.0 - $lookback_seconds
RETURN count(DISTINCT src) AS source_count
"""

# 2. Two-hop connection: does the destination account itself send money onward
# within the lookback window (simple layering/chain pattern)?
TWO_HOP = """
MATCH (dst:Account {account_id: $destination_account_id})
      -[:SENT]->(t2:Transaction)
      -[:RECEIVED_BY]->(next:Account)
WHERE t2.created_ts > timestamp() / 1000.0 - $lookback_seconds
RETURN count(DISTINCT next) AS onward_count
"""

# 3. Recent relationship count: how many distinct accounts did the SOURCE
# account interact with (sent to or received from) recently?
# The aggregation must happen in its own WITH clause: Neo4j rejects mixing
# aggregated and non-aggregated expressions (e.g. size(...) + collect(...))
# in a single RETURN because of implicit grouping keys.
RELATIONSHIP_COUNT = """
MATCH (a:Account {account_id: $account_id})
WITH a, timestamp() / 1000.0 - $lookback_seconds AS since
OPTIONAL MATCH (a)-[:SENT]->(t1:Transaction)-[:RECEIVED_BY]->(out:Account)
WHERE t1.created_ts > since
WITH a, since, collect(DISTINCT out) AS sent_to
OPTIONAL MATCH (frm:Account)-[:SENT]->(t2:Transaction)-[:RECEIVED_BY]->(a)
WHERE t2.created_ts > since
WITH size([x IN sent_to WHERE x IS NOT NULL]) AS sent_count,
     collect(DISTINCT frm) AS received_from
RETURN sent_count
       + size([x IN received_from WHERE x IS NOT NULL]) AS counterparty_count
"""
