"""Phase 14 Part 1 continued: tool registry allowlist and validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.assistant.registry import Tool, ToolRegistry, ToolRegistryError
from backend.app.assistant.schemas import AccountSummaryArgs, RecentTransactionsArgs
from backend.app.assistant.tools import build_tool_registry
from backend.app.llm.models import LLMToolCall, LLMToolSpec


def _noop(args: object, ctx: object) -> dict:
    return {"ok": True}


def _make_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            Tool(
                name="noop_tool",
                description="test tool",
                args_model=AccountSummaryArgs,
                executor=_noop,
            )
        ]
    )


class TestToolRegistry:
    def test_allowlist_rejects_unknown_tool(self) -> None:
        registry = _make_registry()
        for bad in ("execute_cypher", "drop_database", "__import__", "graph_query"):
            with pytest.raises(ToolRegistryError):
                registry.get(bad)

    def test_get_registered_tool(self) -> None:
        assert _make_registry().get("noop_tool").name == "noop_tool"

    def test_list_tools_is_exact_allowlist(self) -> None:
        names = sorted(t.name for t in build_tool_registry().list_tools())
        assert names == [
            "get_account_summary",
            "get_fraud_assessment",
            "get_recent_transactions",
            "get_transaction_details",
        ]

    def test_registry_rejects_duplicate_names(self) -> None:
        tool = Tool(
            name="dup", description="d", args_model=AccountSummaryArgs, executor=_noop
        )
        with pytest.raises(ToolRegistryError):
            ToolRegistry([tool, tool])

    def test_no_write_tools_registered(self) -> None:
        forbidden = {
            "transfer",
            "deposit",
            "withdraw",
            "create_account",
            "close_account",
            "change_password",
            "execute_cypher",
            "run_sql",
            "graph_query",
        }
        names = {t.name for t in build_tool_registry().list_tools()}
        assert not (names & forbidden)

    def test_tool_specs_are_serializable_json_schemas(self) -> None:
        specs = [t.to_spec() for t in build_tool_registry().list_tools()]
        assert all(isinstance(s, LLMToolSpec) for s in specs)
        assert all(s.parameters.get("type") == "object" for s in specs)


class TestToolExecutionValidation:
    def test_tool_call_rejects_unknown_name(self) -> None:
        registry = build_tool_registry()
        call = LLMToolCall(call_id="1", name="admin_tool", arguments="{}")
        with pytest.raises(ToolRegistryError):
            registry.execute(call, ctx=None)

    def test_tool_call_rejects_malformed_arguments(self) -> None:
        registry = build_tool_registry()
        call = LLMToolCall(
            call_id="1",
            name="get_recent_transactions",
            arguments='{"limit": "not-a-number"}',
        )
        with pytest.raises(ValidationError):
            registry.execute(call, ctx=None)

    def test_limit_cannot_exceed_backend_maximum(self) -> None:
        with pytest.raises(ValidationError):
            RecentTransactionsArgs(limit=1000)
