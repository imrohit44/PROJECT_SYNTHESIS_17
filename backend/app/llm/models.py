"""Provider-neutral LLM data structures and assistant contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[LLMToolCall] | None = None


class LLMToolSpec(BaseModel):
    """A single entry of the provider tool list (JSON-schema based)."""

    name: str
    description: str
    parameters: dict[str, Any]


class LLMToolCall(BaseModel):
    call_id: str
    name: str
    arguments: str


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    message: LLMMessage
    usage: LLMUsage = Field(default_factory=LLMUsage)
    finish_reason: str = "stop"
