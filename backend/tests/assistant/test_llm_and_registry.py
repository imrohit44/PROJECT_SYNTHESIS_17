"""Phase 14 Part 1 tests: LLM configuration, provider abstraction, tool schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.assistant.schemas import (
    AccountSummaryArgs,
    FraudAssessmentArgs,
    RecentTransactionsArgs,
    TransactionDetailsArgs,
)
from backend.app.core.config import Settings
from backend.app.llm.client import LLMClient, LLMNotConfiguredError
from backend.app.llm.models import LLMMessage, LLMResponse, LLMToolSpec


class TestLLMConfiguration:
    def test_llm_settings_have_safe_defaults(self) -> None:
        settings = Settings()
        assert settings.llm_provider == ""
        assert settings.llm_api_key == ""
        assert settings.llm_timeout_seconds > 0
        assert settings.llm_max_output_tokens > 0
        assert settings.max_tool_calls_per_request == 3

    def test_max_message_length_bounded(self) -> None:
        settings = Settings()
        assert 1 <= settings.max_assistant_message_length <= 4000


class TestProviderAbstraction:
    def test_client_requires_api_key(self) -> None:
        client = LLMClient(
            api_key="",
            model="test-model",
            base_url="https://example.invalid/v1",
            timeout_seconds=1.0,
            max_output_tokens=16,
        )
        with pytest.raises(LLMNotConfiguredError):
            client.generate_with_tools(
                messages=[LLMMessage(role="user", content="hi")],
                tools=[],
            )

    def test_generate_with_tools_returns_typed_response(self, monkeypatch):
        """Provider transport is mocked; abstraction contract is verified."""

        def fake_post(url, headers, json, timeout):  # noqa: ANN001
            class FakeResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict:
                    return {
                        "choices": [
                            {
                                "message": {"role": "assistant", "content": None},
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    }

            return FakeResponse()

        import backend.app.llm.client as client_module

        monkeypatch.setattr(client_module.httpx, "post", fake_post)
        client = LLMClient(
            api_key="test-key",
            model="test-model",
            base_url="https://example.invalid/v1",
            timeout_seconds=1.0,
            max_output_tokens=16,
        )
        response = client.generate_with_tools(
            messages=[LLMMessage(role="user", content="hi")],
            tools=[LLMToolSpec(name="t", description="d", parameters={})],
        )
        assert isinstance(response, LLMResponse)
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 5
        assert response.message.role == "assistant"


class TestToolSchemas:
    def test_recent_transactions_limit_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RecentTransactionsArgs(limit=0)
        with pytest.raises(ValidationError):
            RecentTransactionsArgs(limit=51)
        assert RecentTransactionsArgs(limit=50).limit == 50
        assert RecentTransactionsArgs().limit == 10

    def test_transaction_id_required(self) -> None:
        with pytest.raises(ValidationError):
            TransactionDetailsArgs(transaction_id="")
        assert TransactionDetailsArgs(transaction_id="tx-1").transaction_id == "tx-1"

    def test_account_summary_and_fraud_args_accept_no_input(self) -> None:
        assert AccountSummaryArgs() is not None
        assert FraudAssessmentArgs(transaction_id="tx-9").transaction_id == "tx-9"

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RecentTransactionsArgs(limit=5, customer_id="attacker")  # type: ignore[call-arg]
