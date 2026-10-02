"""Pydantic input schemas for every registered assistant tool."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Hard backend maximum regardless of what the LLM requests.
MAX_TRANSACTION_LIMIT = 50

# Unknown fields are rejected: the model cannot smuggle identity or
# authority overrides (customer_id, role, ...) into a tool call.
_STRICT = ConfigDict(extra="forbid")


class AccountSummaryArgs(BaseModel):
    model_config = _STRICT


class RecentTransactionsArgs(BaseModel):
    model_config = _STRICT

    limit: int = Field(default=10, ge=1, le=MAX_TRANSACTION_LIMIT)
    # Optional narrowing only: ownership is re-validated by the backend.
    account_id: str | None = Field(default=None, min_length=1, max_length=64)


class TransactionDetailsArgs(BaseModel):
    model_config = _STRICT

    transaction_id: str = Field(min_length=1, max_length=64)


class FraudAssessmentArgs(BaseModel):
    model_config = _STRICT

    transaction_id: str = Field(min_length=1, max_length=64)


# --- API-level contracts ---


class ToolCallStatus(StrEnum):
    """Mirrors the agent-level statuses exposed in the chat response."""

    SUCCESS = "success"
    ERROR = "error"
    FAILED = "failed"


class ToolCallRecord(BaseModel):
    tool: str
    status: ToolCallStatus = ToolCallStatus.SUCCESS
    detail: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


# Which assistant answers a request: the configured LLM provider, or the
# deterministic fallback that runs when no provider is configured. The client
# only ever learns the mode, never any provider detail.
AssistantMode = Literal["llm", "fallback"]
MODE_LLM: AssistantMode = "llm"
MODE_FALLBACK: AssistantMode = "fallback"


class AssistantStatus(BaseModel):
    """Availability of the assistant and the mode that answers."""

    available: bool = True
    mode: AssistantMode


class ChatResponse(BaseModel):
    response: str
    conversation_id: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    mode: AssistantMode | None = None
