"""Provider-neutral LLM client abstraction (Phase 14).

The rest of the application depends only on ``LLMClient``. Provider details
(credentials, endpoints, SDKs) stay behind this interface. The initial
implementation speaks the OpenAI-compatible chat-completions protocol with
native tool calling over httpx, which works with many providers.
"""

from __future__ import annotations

from typing import Any

import httpx

from .models import LLMMessage, LLMResponse, LLMToolCall, LLMToolSpec, LLMUsage

COMPLETIONS_PATH = "/chat/completions"


class LLMError(Exception):
    """Raised when the LLM provider is unavailable or misconfigured."""


class LLMNotConfiguredError(LLMError):
    """Raised when LLM_PROVIDER/LLM_API_KEY are missing (agent disabled)."""


class LLMClient:
    """OpenAI-compatible chat-completions client with native tool calling."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_output_tokens = max_output_tokens

    @property
    def model(self) -> str:
        return self._model

    def _extract_tool_calls(self, raw_message: dict[str, Any]) -> list[LLMToolCall]:
        calls: list[LLMToolCall] = []
        for call in raw_message.get("tool_calls") or []:
            function = call.get("function") or {}
            name = function.get("name")
            if not name:
                raise LLMError("provider returned a tool call without a name")
            calls.append(
                LLMToolCall(
                    call_id=str(call.get("id") or ""),
                    name=str(name),
                    arguments=function.get("arguments") or "{}",
                )
            )
        return calls

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec],
    ) -> LLMResponse:
        if not self._api_key or not self._model:
            raise LLMNotConfiguredError(
                "LLM provider is not configured (LLM_PROVIDER/LLM_API_KEY)"
            )

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    **(
                        {"tool_call_id": message.tool_call_id}
                        if message.tool_call_id
                        else {}
                    ),
                    **(
                        {"tool_calls": message.tool_calls} if message.tool_calls else {}
                    ),
                }
                for message in messages
            ],
            "max_tokens": self._max_output_tokens,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]

        try:
            response = httpx.post(
                f"{self._base_url}{COMPLETIONS_PATH}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as error:
            raise LLMError(f"LLM provider returned an error: {error}") from error
        except (httpx.HTTPError, ValueError) as error:
            raise LLMError(f"LLM provider request failed: {error}") from error

        try:
            choice = body["choices"][0]
            raw_message = choice["message"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("LLM provider returned a malformed response") from error

        usage = body.get("usage") or {}
        return LLMResponse(
            message=LLMMessage(
                role="assistant",
                content=raw_message.get("content"),
                tool_calls=self._extract_tool_calls(raw_message) or None,
            ),
            usage=LLMUsage(
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
            finish_reason=str(choice.get("finish_reason") or "stop"),
        )
