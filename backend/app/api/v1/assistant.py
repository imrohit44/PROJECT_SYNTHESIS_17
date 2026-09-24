"""Phase 14 API: read-only banking assistant.

The LLM proposes tool calls; this layer builds the authorization context from
the authenticated JWT principal, so the model can never supply identity. The
assistant is optional: when LLM configuration is absent the endpoint returns an
explicit 503 while the rest of the banking API is unaffected.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.auth_dependencies import get_current_user
from backend.app.api.dependencies import (
    get_assistant_limiter,
    get_bank,
    get_llm_client,
)
from backend.app.application.banking import BankApplicationService
from backend.app.assistant.agent import (
    AgentService,
    AgentToolsExceededError,
)
from backend.app.assistant.metrics import record_chat, record_tool_call
from backend.app.assistant.registry import AgentContext
from backend.app.assistant.schemas import (
    ChatRequest,
    ChatResponse,
    ToolCallRecord,
    ToolCallStatus,
)
from backend.app.assistant.tools import build_tool_registry
from backend.app.core.config import get_settings
from backend.app.llm.client import LLMClient, LLMError, LLMNotConfiguredError
from backend.app.security.principal import CurrentUser
from backend.app.security.rate_limit import LoginRateLimiter
from services.common.tracing import get_tracer

router = APIRouter(prefix="/assistant", tags=["assistant"])

logger = structlog.get_logger(__name__)

# Tools whose names may appear as Prometheus label values. Model-proposed
# names outside the allowlist are bucketed to keep label cardinality bounded.
_STATUS_MAP = {
    "success": ToolCallStatus.SUCCESS,
    "error": ToolCallStatus.ERROR,
}


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask the read-only banking assistant",
)
def chat(
    request: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    bank: BankApplicationService = Depends(get_bank),
    limiter: LoginRateLimiter = Depends(get_assistant_limiter),
    llm: LLMClient = Depends(get_llm_client),
) -> ChatResponse:
    """Answer one banking question using allowlisted read-only tools."""
    settings = get_settings()
    if len(request.message) > settings.max_assistant_message_length:
        record_chat("rejected")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Message is too long",
        )

    if not limiter.allow(f"assistant:{user.user_id}"):
        record_chat("rejected")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many assistant requests",
        )

    registry = build_tool_registry()
    known_tools = {tool.name for tool in registry.list_tools()}
    context = AgentContext(
        user=user,
        bank=bank,
        fraud_service_url=settings.fraud_service_url,
        timeout=settings.fraud_service_timeout_seconds,
    )
    agent = AgentService(llm=llm, registry=registry, settings=settings)

    tracer = get_tracer(__name__)
    try:
        with tracer.start_as_current_span("assistant.chat") as span:
            result = agent.run(request.message, context)
            span.set_attribute("pybank.assistant.tool_calls", len(result.tool_calls))
    except LLMNotConfiguredError as error:
        logger.warning("assistant_not_configured")
        record_chat("not_configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The banking assistant is not configured",
        ) from error
    except LLMError as error:
        logger.warning("assistant_llm_error")
        record_chat("llm_error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The banking assistant is temporarily unavailable",
        ) from error
    except AgentToolsExceededError as error:
        logger.warning("assistant_tools_exceeded", max_rounds=agent.max_tool_rounds)
        record_chat("rejected")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The assistant could not complete the request",
        ) from error

    records: list[ToolCallRecord] = []
    for call in result.tool_calls:
        label = call.tool if call.tool in known_tools else "unknown"
        record_tool_call(label, call.status)
        records.append(
            ToolCallRecord(
                tool=call.tool,
                status=_STATUS_MAP.get(call.status, ToolCallStatus.ERROR),
                detail=call.detail,
            )
        )

    record_chat("success")
    logger.info(
        "assistant_chat_completed",
        tool_calls=len(records),
        rounds=result.rounds,
        model=result.model,
        prompt_version=result.prompt_version,
    )
    return ChatResponse(response=result.response, tool_calls=records)
