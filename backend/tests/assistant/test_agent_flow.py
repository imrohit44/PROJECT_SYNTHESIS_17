"""Phase 14 Part 2 tests: agent flow with mocked LLM (deterministic, no paid API)."""

from __future__ import annotations

import pytest

from backend.app.assistant.agent import AgentService, AgentToolsExceededError
from backend.app.llm.models import LLMMessage, LLMResponse, LLMToolCall, LLMUsage


class MockLLM:
    """Scripted LLM: returns queued responses regardless of input."""

    model = "mock-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    def generate_with_tools(self, messages, tools):  # noqa: ANN001
        self.calls.append(list(messages))
        if not self._responses:
            raise AssertionError("mock LLM exhausted")
        return self._responses.pop(0)


def _tool_response(call: LLMToolCall) -> LLMResponse:
    return LLMResponse(
        message=LLMMessage(
            role="assistant",
            content=None,
            tool_calls=[call],
        ),
        usage=LLMUsage(input_tokens=5, output_tokens=5),
        finish_reason="tool_calls",
    )


def _final_response(content: str) -> LLMResponse:
    return LLMResponse(
        message=LLMMessage(role="assistant", content=content),
        usage=LLMUsage(input_tokens=5, output_tokens=5),
        finish_reason="stop",
    )


class _FakeCtx:
    """Minimal agent context stand-in for tool-less flows."""

    user = None
    bank = None
    fraud_service_url = "http://fraud:8001"
    timeout = 1.0


class TestAgentFlow:
    def test_direct_answer_without_tools(self) -> None:
        llm = MockLLM([_final_response("Hello! How can I help?")])
        service = AgentService(llm=llm, registry=None, settings=None)
        result = service.run(message="hi", ctx=_FakeCtx())
        assert result.response == "Hello! How can I help?"
        assert result.tool_calls == []

    def test_tool_selection_and_final_answer(self) -> None:
        llm = MockLLM(
            [
                _tool_response(
                    LLMToolCall(
                        call_id="c1",
                        name="get_account_summary",
                        arguments="{}",
                    )
                ),
                _final_response("Your balance is 100.00."),
            ]
        )
        calls: list[dict] = []

        def fake_executor(args, ctx):  # noqa: ANN001
            calls.append(args)
            return {"balance": 100.0, "currency": "USD"}

        from backend.app.assistant.registry import Tool, ToolRegistry
        from backend.app.assistant.schemas import AccountSummaryArgs

        registry = ToolRegistry(
            [
                Tool(
                    name="get_account_summary",
                    description="d",
                    args_model=AccountSummaryArgs,
                    executor=fake_executor,
                )
            ]
        )
        service = AgentService(llm=llm, registry=registry, settings=None)
        result = service.run(message="What is my balance?", ctx=_FakeCtx())
        assert result.response == "Your balance is 100.00."
        assert [t.tool for t in result.tool_calls] == ["get_account_summary"]
        assert result.tool_calls[0].status == "success"
        assert len(calls) == 1

    def test_unknown_tool_is_rejected_not_executed(self) -> None:
        llm = MockLLM(
            [
                _tool_response(
                    LLMToolCall(call_id="c1", name="drop_database", arguments="{}")
                ),
                _final_response("I cannot do that."),
            ]
        )
        from backend.app.assistant.registry import Tool, ToolRegistry
        from backend.app.assistant.schemas import AccountSummaryArgs

        registry = ToolRegistry(
            [
                Tool(
                    name="get_account_summary",
                    description="d",
                    args_model=AccountSummaryArgs,
                    executor=lambda a, c: {},
                )
            ]
        )
        service = AgentService(llm=llm, registry=registry, settings=None)
        result = service.run(message="drop everything", ctx=_FakeCtx())
        assert result.tool_calls[0].status == "error"
        assert result.tool_calls[0].tool == "drop_database"

    def test_tool_call_limit_enforced(self) -> None:
        """A model that never stops calling tools must terminate safely."""
        responses = [
            _tool_response(
                LLMToolCall(call_id=f"c{i}", name="get_account_summary", arguments="{}")
            )
            for i in range(6)
        ]
        llm = MockLLM(responses)
        from backend.app.assistant.registry import Tool, ToolRegistry
        from backend.app.assistant.schemas import AccountSummaryArgs

        registry = ToolRegistry(
            [
                Tool(
                    name="get_account_summary",
                    description="d",
                    args_model=AccountSummaryArgs,
                    executor=lambda a, c: {"ok": True},
                )
            ]
        )
        service = AgentService(llm=llm, registry=registry, settings=None)
        with pytest.raises(AgentToolsExceededError):
            service.run(message="loop", ctx=_FakeCtx())
        assert len(llm.calls) <= 4  # initial + MAX 3 tool rounds

    def test_system_prompt_is_versioned_and_read_only(self) -> None:
        from backend.app.assistant.prompts import PROMPT_VERSION, SYSTEM_PROMPT

        assert PROMPT_VERSION == "banking-agent-v1"
        assert (
            "read-only" in SYSTEM_PROMPT.lower() or "read only" in SYSTEM_PROMPT.lower()
        )
        assert "never" in SYSTEM_PROMPT.lower()
        assert "transfer" in SYSTEM_PROMPT.lower()
