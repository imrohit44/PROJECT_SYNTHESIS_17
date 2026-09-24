"""Phase 14 agent loop: controlled tool calling over the allowlisted registry.

The LLM chooses *what information is needed*; the backend decides *what is
allowed*. Every tool call is matched against the explicit registry, validated
with Pydantic, and executed against backend-built authorization context.

There is no dynamic code execution and no dynamic import: unknown tool names
are rejected, never resolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from pydantic import ValidationError

from backend.app.assistant.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from backend.app.assistant.registry import AgentContext, ToolRegistry, ToolRegistryError
from backend.app.llm.models import LLMMessage, LLMToolCall

logger = structlog.get_logger(__name__)

# Hard ceiling on tool rounds per user request (initial call + MAX rounds).
DEFAULT_MAX_TOOL_ROUNDS = 3


class AgentError(Exception):
    """Base class for assistant agent failures."""


class AgentToolsExceededError(AgentError):
    """Raised when the model keeps calling tools past the hard limit."""


@dataclass
class AgentToolCall:
    """Sanitized record of one attempted tool call."""

    tool: str
    status: str  # success | error
    detail: str | None = None


@dataclass
class AgentResult:
    """Final assistant answer plus the tool calls that produced it."""

    response: str
    tool_calls: list[AgentToolCall] = field(default_factory=list)
    rounds: int = 0
    prompt_version: str = PROMPT_VERSION
    model: str | None = None


class AgentService:
    """Runs one bounded tool-calling conversation turn."""

    def __init__(
        self,
        llm: Any,
        registry: ToolRegistry | None,
        settings: Any = None,
        max_tool_rounds: int | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        if max_tool_rounds is not None:
            rounds: int = max_tool_rounds
        elif settings is not None:
            configured = getattr(settings, "max_tool_calls_per_request", None)
            if configured is None:
                rounds = DEFAULT_MAX_TOOL_ROUNDS
            else:
                rounds = int(configured)
        else:
            rounds = DEFAULT_MAX_TOOL_ROUNDS
        self._max_tool_rounds = max(1, int(rounds))

    @property
    def max_tool_rounds(self) -> int:
        return self._max_tool_rounds

    def _tool_specs(self) -> list[Any]:
        if self._registry is None:
            return []
        return [tool.to_spec() for tool in self._registry.list_tools()]

    def _execute(self, call: LLMToolCall, ctx: Any) -> tuple[Any, AgentToolCall]:
        """Execute one validated tool call; failures become observations."""
        if self._registry is None:
            return None, AgentToolCall(
                tool=call.name, status="error", detail="No tools are available"
            )
        try:
            result = self._registry.execute(call, ctx)
        except ToolRegistryError as error:
            logger.warning("assistant_tool_rejected", tool=call.name, reason=str(error))
            return None, AgentToolCall(
                tool=call.name, status="error", detail=str(error)
            )
        except ValidationError:
            logger.warning("assistant_tool_invalid_arguments", tool=call.name)
            return None, AgentToolCall(
                tool=call.name, status="error", detail="Invalid tool arguments"
            )
        except Exception:  # noqa: BLE001 - tool boundary: never leak internals
            logger.warning("assistant_tool_failed", tool=call.name)
            return None, AgentToolCall(
                tool=call.name, status="error", detail="Tool execution failed"
            )
        return result, AgentToolCall(tool=call.name, status="success")

    def run(self, message: str, ctx: AgentContext | Any) -> AgentResult:
        """Answer one user message, running at most ``max_tool_rounds`` rounds."""
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=message),
        ]
        specs = self._tool_specs()
        records: list[AgentToolCall] = []
        rounds = 0

        while True:
            response = self._llm.generate_with_tools(messages=messages, tools=specs)
            assistant_message = response.message
            tool_calls = assistant_message.tool_calls or []

            if not tool_calls:
                return AgentResult(
                    response=assistant_message.content or "",
                    tool_calls=records,
                    rounds=rounds,
                    prompt_version=PROMPT_VERSION,
                    model=getattr(self._llm, "model", None),
                )

            rounds += 1
            if rounds > self._max_tool_rounds:
                logger.warning(
                    "assistant_tool_limit_exceeded", max_rounds=self._max_tool_rounds
                )
                raise AgentToolsExceededError(
                    f"Assistant exceeded {self._max_tool_rounds} tool rounds"
                )

            messages.append(assistant_message)
            for call in tool_calls:
                result, record = self._execute(call, ctx)
                records.append(record)
                messages.append(
                    LLMMessage(
                        role="tool",
                        content=_serialize_tool_result(result, record),
                        tool_call_id=call.call_id,
                    )
                )


def _serialize_tool_result(result: Any, record: AgentToolCall) -> str:
    """Render a tool observation for the model as a compact JSON string."""
    import json

    if record.status != "success":
        return json.dumps({"error": record.detail or "tool failed"})
    return json.dumps(result, default=str)
