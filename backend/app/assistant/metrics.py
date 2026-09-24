"""Prometheus metrics for the read-only banking assistant (Phase 14).

Labels are bounded; user, customer, and transaction identifiers are never
used as labels.
"""

from prometheus_client import Counter

ASSISTANT_CHATS_TOTAL = Counter(
    "assistant_chats_total",
    "Total assistant chat requests",
    ["status"],  # success | rejected | llm_error | not_configured
)
ASSISTANT_TOOL_CALLS_TOTAL = Counter(
    "assistant_tool_calls_total",
    "Total assistant tool executions",
    ["tool", "status"],  # success | rejected | failed
)


def record_chat(status: str) -> None:
    ASSISTANT_CHATS_TOTAL.labels(status=status).inc()


def record_tool_call(tool: str, status: str) -> None:
    ASSISTANT_TOOL_CALLS_TOTAL.labels(tool=tool, status=status).inc()
