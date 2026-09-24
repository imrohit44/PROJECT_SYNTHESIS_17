"""Explicit tool registry — the capability boundary of the assistant."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from backend.app.llm.models import LLMToolCall, LLMToolSpec


class ToolRegistryError(Exception):
    """Raised when the registry is misconfigured or a tool name is unknown."""


class ToolArgumentError(ToolRegistryError):
    """Raised when a model tool call carries arguments that are not a JSON object."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    executor: Any  # callable(args, context) -> dict
    spec: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "spec",
            {
                "name": self.name,
                "description": self.description,
                "input_schema": self.args_model.model_json_schema(),
            },
        )

    def to_spec(self) -> LLMToolSpec:
        """Provider-facing JSON-schema descriptor for this tool."""
        return LLMToolSpec(
            name=self.name,
            description=self.description,
            parameters=dict(self.spec["input_schema"]),
        )

    def parse_arguments(self, arguments: str | dict[str, Any] | None) -> BaseModel:
        """Validate model-supplied arguments.

        Raises ``ToolArgumentError`` when the payload is not a JSON object and
        ``pydantic.ValidationError`` when the fields are invalid.
        """
        if arguments is None or arguments == "":
            raw: Any = {}
        elif isinstance(arguments, str):
            try:
                raw = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise ToolArgumentError("Tool arguments are not valid JSON") from error
        else:
            raw = arguments
        if not isinstance(raw, dict):
            raise ToolArgumentError("Tool arguments must be a JSON object")
        return self.args_model.model_validate(raw)


class ToolRegistry:
    """Allowlist-only registry. Unknown tool names are always rejected."""

    def __init__(self, tools: list[Tool]) -> None:
        registry: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in registry:
                raise ToolRegistryError(f"Duplicate tool name: {tool.name}")
            registry[tool.name] = tool
        self._tools = registry

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get(self, name: str) -> Tool:
        """Return a registered tool by name.

        Unknown names always raise: the model can never reach code that is not
        on the explicit allowlist, and nothing is imported dynamically.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolRegistryError(f"Unknown tool: {name}")
        return tool

    def execute(self, call: LLMToolCall, ctx: Any) -> Any:
        """Validate and execute one model tool call.

        Raises ``ToolRegistryError`` for unknown/malformed tool names and
        ``pydantic.ValidationError`` for invalid arguments.
        """
        tool = self.get(call.name)
        args = tool.parse_arguments(call.arguments)
        return tool.executor(args, ctx)


class AgentContext:
    """Backend-owned identity and dependencies passed to every tool.

    The LLM can never populate this — it is built from the authenticated
    JWT principal and the existing application services.
    """

    def __init__(
        self, user: Any, bank: Any, fraud_service_url: str, timeout: float
    ) -> None:
        self.user = user
        self.bank = bank
        self.fraud_service_url = fraud_service_url.rstrip("/")
        self.timeout = timeout
