"""Deterministic fallback assistant: intent routing, safety, and ownership.

The fallback answers through the same agent, registry, and tools as the LLM
path, so these tests drive the real stack: fallback -> AgentService ->
ToolRegistry -> read-only tools -> SQLite banking data.
"""

from __future__ import annotations

from typing import Any

import pytest

import backend.app.assistant.tools as tools_module
from backend.app.application.banking import BankApplicationService
from backend.app.assistant.agent import AgentResult, AgentService
from backend.app.assistant.fallback import (
    FALLBACK_MODEL,
    DeterministicBankingAssistant,
    classify_intent,
    select_engine,
)
from backend.app.assistant.registry import AgentContext
from backend.app.assistant.tools import build_tool_registry
from backend.app.llm.client import LLMClient
from backend.app.security.principal import CurrentUser
from backend.app.security.roles import UserRole

READ_ONLY_TOOLS = {
    "get_account_summary",
    "get_recent_transactions",
    "get_transaction_details",
    "get_fraud_assessment",
}


def _context(
    bank: BankApplicationService,
    customer_id: str,
    role: UserRole = UserRole.CUSTOMER,
) -> AgentContext:
    """Build the backend-owned context exactly as the API layer does."""
    user = CurrentUser(
        user_id=f"user-{customer_id}",
        customer_id=customer_id,
        email="owner@example.com",
        role=role,
    )
    return AgentContext(
        user=user,
        bank=bank,
        fraud_service_url="http://fraud.invalid",
        timeout=0.5,
    )


@pytest.fixture
def customers(bank_service: BankApplicationService) -> dict[str, Any]:
    """Alice and Bob, each with one funded savings account."""
    alice = bank_service.register_customer("Alice", "alice@example.com")
    bob = bank_service.register_customer("Bob", "bob@example.com")
    alice_account = bank_service.create_savings_account(alice.customer_id, "100.00")
    bob_account = bank_service.create_savings_account(bob.customer_id, "500.00")
    bank_service.deposit(alice_account.account_id, "25.00")
    bank_service.deposit(bob_account.account_id, "400.00")
    alice_tx = bank_service.list_transactions(alice_account.account_id)[0]
    bob_tx = bank_service.list_transactions(bob_account.account_id)[0]
    return {
        "bank": bank_service,
        "alice_ctx": _context(bank_service, alice.customer_id),
        "bob_ctx": _context(bank_service, bob.customer_id),
        "alice_account_id": alice_account.account_id,
        "alice_transaction_id": alice_tx.transaction_id,
        "bob_account_id": bob_account.account_id,
        "bob_transaction_id": bob_tx.transaction_id,
    }


def _ask(message: str, ctx: AgentContext) -> AgentResult:
    """Run one message through the agent exactly as the endpoint does."""
    agent = AgentService(
        llm=DeterministicBankingAssistant(),
        registry=build_tool_registry(),
        settings=None,
    )
    return agent.run(message, ctx)


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class TestIntentRouting:
    def test_balance_question_reads_the_account_summary(self, customers) -> None:
        result = _ask("what is my balance?", customers["alice_ctx"])

        assert [call.tool for call in result.tool_calls] == ["get_account_summary"]
        assert result.response.startswith("Your accounts:")
        assert "125.00" in result.response

    def test_recent_transactions_question_reads_transactions(self, customers) -> None:
        result = _ask("show recent transactions", customers["alice_ctx"])

        assert [call.tool for call in result.tool_calls] == ["get_recent_transactions"]
        assert result.response.startswith("Recent transactions:")
        assert customers["alice_transaction_id"] not in result.response

    def test_account_details_question_reads_the_account_tool(self, customers) -> None:
        result = _ask("show account details", customers["alice_ctx"])

        assert [call.tool for call in result.tool_calls] == ["get_account_summary"]
        assert "Savings account" in result.response

    def test_risk_question_assesses_the_newest_owned_transaction(
        self, customers, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        requested: list[str] = []

        def fake_get(url: str, timeout: float = 0.0) -> _FakeResponse:
            requested.append(url)
            return _FakeResponse(
                {"risk_level": "LOW", "final_score": 0.12, "reasons": ["rule"]}
            )

        monkeypatch.setattr(tools_module.httpx, "get", fake_get)
        result = _ask("what is my risk status?", customers["alice_ctx"])

        assert [call.tool for call in result.tool_calls] == [
            "get_recent_transactions",
            "get_fraud_assessment",
        ]
        assert result.response.startswith("Risk status")
        assert "low" in result.response
        assert customers["alice_transaction_id"] in requested[0]

    def test_help_lists_capabilities_without_touching_data(self, customers) -> None:
        result = _ask("what can you do", customers["alice_ctx"])

        assert result.tool_calls == []
        assert "account summary" in result.response
        assert "risk status" in result.response

    def test_unsupported_question_returns_guidance_without_inventing(
        self, customers
    ) -> None:
        result = _ask("what is the weather in Mumbai?", customers["alice_ctx"])

        assert result.tool_calls == []
        assert "account summary" in result.response
        assert "weather" not in result.response.lower()
        assert "125.00" not in result.response

    def test_unknown_intent_is_classified_as_unknown(self) -> None:
        assert classify_intent("tell me a joke") == "unknown"
        assert classify_intent("show my balance") == "accounts"


class TestSafetyAndOwnership:
    """The fallback is read-only, and scoped exactly like the LLM path."""

    def test_only_the_callers_own_data_is_returned(self, customers) -> None:
        result = _ask("show my accounts", customers["alice_ctx"])

        assert "125.00" in result.response
        assert customers["bob_account_id"] not in result.response
        assert "500.00" not in result.response

    def test_another_customers_transaction_id_cannot_be_used(self, customers) -> None:
        """A foreign id typed by the user changes nothing."""
        result = _ask(
            f"show my transactions for {customers['bob_transaction_id']}",
            customers["alice_ctx"],
        )

        assert [call.tool for call in result.tool_calls] == ["get_recent_transactions"]
        assert customers["bob_transaction_id"] not in result.response
        assert customers["bob_account_id"] not in result.response

    def test_no_write_operation_is_ever_requested(self, customers) -> None:
        for message in (
            "transfer 5000 to another account",
            "withdraw all my money",
            "freeze my account",
            "delete my profile",
            "show my balance",
        ):
            result = _ask(message, customers["alice_ctx"])
            for call in result.tool_calls:
                assert call.tool in READ_ONLY_TOOLS

    def test_tool_failure_becomes_a_safe_message(
        self, customers, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def unavailable(url: str, timeout: float = 0.0) -> _FakeResponse:
            raise tools_module.httpx.ConnectError("connection refused")

        monkeypatch.setattr(tools_module.httpx, "get", unavailable)
        result = _ask("show my fraud assessment", customers["alice_ctx"])

        assert "couldn't retrieve your account information" in result.response
        assert "Traceback" not in result.response
        assert "fraud.invalid" not in result.response
        assert "ConnectError" not in result.response


class TestProviderSelection:
    def test_configured_provider_keeps_the_llm_path(self) -> None:
        provider = LLMClient(
            api_key="configured-key",
            model="configured-model",
            base_url="https://llm.example/v1",
            timeout_seconds=1.0,
            max_output_tokens=16,
        )

        engine, mode = select_engine(provider)

        assert engine is provider
        assert mode == "llm"

    def test_unconfigured_provider_selects_the_fallback(self) -> None:
        provider = LLMClient(
            api_key="",
            model="unused",
            base_url="https://llm.invalid/v1",
            timeout_seconds=1.0,
            max_output_tokens=16,
        )

        engine, mode = select_engine(provider)

        assert isinstance(engine, DeterministicBankingAssistant)
        assert engine.model == FALLBACK_MODEL
        assert mode == "fallback"
