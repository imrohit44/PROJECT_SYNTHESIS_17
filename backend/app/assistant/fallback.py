"""Lightweight deterministic fallback for the read-only banking assistant.

Phase 14 answers questions through a configured LLM provider. Without provider
credentials the endpoint is a dead end even though every read-only tool and all
of the banking data are available.

This module adds a small deterministic assistant that plugs into the *same*
seam as the real provider: it exposes ``generate_with_tools(...)`` and a
``model`` attribute, so ``AgentService``, the allowlist registry, and the
JWT-derived ``AgentContext`` are reused exactly as they are for the LLM. No
part of Phase 14 changes.

Rules this module keeps:

* Ordinary Python only: no model, no network call, no new dependency, no
  infrastructure.
* No invented facts: every rendered value comes from a tool observation
  produced by the existing read-only tools.
* No widened access: the fallback proposes tool *names* and bounded arguments
  only. Identity, ownership, and rate limits stay with the backend.
* Intentionally narrow: anything unrecognised is answered with the list of
  supported operations instead of a guess.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.assistant.schemas import MODE_FALLBACK, MODE_LLM, AssistantMode
from backend.app.llm.models import LLMMessage, LLMResponse, LLMToolCall

# Reported as the "model" so logs show what actually answered a request.
FALLBACK_MODEL = "deterministic-banking-fallback-v1"

_TOOL_SUMMARY = "get_account_summary"
_TOOL_TRANSACTIONS = "get_recent_transactions"
_TOOL_TRANSACTION_DETAILS = "get_transaction_details"
_TOOL_FRAUD = "get_fraud_assessment"

# The only tools the fallback may ever ask for: the frozen read-only allowlist.
_READ_ONLY_TOOLS = frozenset(
    {
        _TOOL_SUMMARY,
        _TOOL_TRANSACTIONS,
        _TOOL_TRANSACTION_DETAILS,
        _TOOL_FRAUD,
    }
)

_TRANSACTION_LIMIT = 10
# Risk questions look at the newest few transactions and assess the latest one.
_RISK_LOOKBACK = 5

_HELP_TEXT = (
    "I can help with your account summary, recent transactions, account "
    "details, and fraud/risk status.\n\n"
    "Try asking:\n"
    "• What is my balance?\n"
    "• Show my recent transactions.\n"
    "• Show my account details.\n"
    "• What is my risk status?\n"
    "• Help"
)

_UNSUPPORTED_TEXT = (
    "I can only read your own banking data, and only for these requests:\n\n"
    + _HELP_TEXT
)

_UNAVAILABLE_TEXT = (
    "I couldn't retrieve your account information right now. Please try again."
)

_NO_TRANSACTIONS_TEXT = "I couldn't find any recent transactions to check."

_NO_ASSESSMENT_TEXT = (
    "No risk assessment is available for your most recent transaction yet."
)

# Ordered intent table. First match wins, so the more specific intents come
# first. A keyword matches when every one of its words appears in the message.
_INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "help",
        (
            "help",
            "what can you do",
            "what can i ask",
            "what do you do",
            "capabilities",
            "who are you",
            "how do you work",
        ),
    ),
    (
        "risk",
        (
            "fraud",
            "risk",
            "flagged",
            "flag",
            "suspicious",
            "assessment",
            "scam",
        ),
    ),
    (
        "transactions",
        (
            "transactions",
            "transaction",
            "recent",
            "latest",
            "history",
            "statement",
            "activity",
            "spend",
            "spent",
        ),
    ),
    (
        "accounts",
        (
            "balance",
            "balances",
            "accounts",
            "account",
            "how much",
            "savings",
            "details",
            "summary",
            "money",
            "total",
        ),
    ),
)


def _tokens(text: str) -> set[str]:
    """Lower-case word tokens; every non-alphanumeric character separates."""
    cleaned = "".join(character if character.isalnum() else " " for character in text)
    return {token for token in cleaned.lower().split() if token}


def classify_intent(message: str) -> str:
    """Map one message to a banking intent, or ``unknown``."""
    words = _tokens(message)
    for name, keywords in _INTENT_KEYWORDS:
        for keyword in keywords:
            if set(keyword.split()) <= words:
                return name
    return "unknown"


class DeterministicBankingAssistant:
    """Answers a narrow set of banking questions without any model.

    It is driven entirely by the message list the agent hands it, so it holds
    no state between requests and cannot accumulate user data.
    """

    model = FALLBACK_MODEL

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[Any],
    ) -> LLMResponse:
        available = {tool.name for tool in tools} & _READ_ONLY_TOOLS
        intent = classify_intent(_last_user_message(messages))
        observations = _observations(messages)

        if not observations:
            return _plan(intent, available)

        follow_up = _follow_up(intent, observations, available)
        if follow_up is not None:
            return follow_up
        return _answer(_render(intent, observations))


def select_engine(provider: Any) -> tuple[Any, AssistantMode]:  # noqa: ANN401
    """Choose the assistant engine and report the mode it runs in.

    A configured provider keeps the Phase 14 path untouched. A provider without
    credentials falls back to the deterministic assistant, so the banking demo
    never dead-ends on missing configuration. Anything that does not report the
    flag at all is treated as a working provider, which keeps the Phase 14
    contract unchanged for anything else.
    """
    if getattr(provider, "is_configured", True):
        return provider, MODE_LLM
    return DeterministicBankingAssistant(), MODE_FALLBACK


def _last_user_message(messages: list[LLMMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user" and message.content:
            return message.content
    return ""


def _decode(content: str | None) -> Any:  # noqa: ANN401
    """Read one tool observation; anything unreadable counts as a failure."""
    if not content:
        return {"error": "unavailable"}
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return {"error": "unavailable"}


def _observations(messages: list[LLMMessage]) -> list[tuple[str, Any]]:
    """Pair each tool observation with the tool that produced it."""
    names_by_call_id: dict[str, str] = {}
    observations: list[tuple[str, Any]] = []
    for message in messages:
        if message.role == "assistant" and message.tool_calls:
            for call in message.tool_calls:
                names_by_call_id[call.call_id] = call.name
        elif message.role == "tool":
            name = names_by_call_id.get(message.tool_call_id or "", "unknown")
            observations.append((name, _decode(message.content)))
    return observations


def _plan(intent: str, available: Any) -> LLMResponse:
    """First round: propose the one read-only tool that answers the intent."""
    if intent == "help":
        return _answer(_HELP_TEXT)
    if intent == "risk" and _TOOL_TRANSACTIONS in available:
        return _tool_call(_TOOL_TRANSACTIONS, {"limit": _RISK_LOOKBACK})
    if intent == "transactions" and _TOOL_TRANSACTIONS in available:
        return _tool_call(_TOOL_TRANSACTIONS, {"limit": _TRANSACTION_LIMIT})
    if intent == "accounts" and _TOOL_SUMMARY in available:
        return _tool_call(_TOOL_SUMMARY, {})
    return _answer(_UNSUPPORTED_TEXT)


def _follow_up(
    intent: str,
    observations: list[tuple[str, Any]],
    available: Any,
) -> LLMResponse | None:
    """Second round for a risk question: assess the newest owned transaction.

    The transaction id comes from the transactions tool's own observation of
    the caller's accounts, never from the user's message, so the fallback
    cannot widen access by typing an id.
    """
    if intent != "risk" or _TOOL_FRAUD not in available:
        return None
    if any(name == _TOOL_FRAUD for name, _ in observations):
        return None
    transaction_id = _newest_transaction_id(observations)
    if transaction_id is None:
        return None
    return _tool_call(_TOOL_FRAUD, {"transaction_id": transaction_id})


def _render(intent: str, observations: list[tuple[str, Any]]) -> str:
    """Turn the tool observations into the reply the user reads."""
    if any(_is_failure(payload) for _, payload in observations):
        return _UNAVAILABLE_TEXT
    if intent == "risk":
        return _render_risk(observations)
    if intent == "transactions":
        return _render_transactions(observations)
    if intent == "accounts":
        return _render_accounts(observations)
    return _UNSUPPORTED_TEXT


def _render_accounts(observations: list[tuple[str, Any]]) -> str:
    accounts = _records(_last_payload(observations, _TOOL_SUMMARY), "accounts")
    if not accounts:
        return "You do not have any accounts yet."

    lines = ["Your accounts:", ""]
    total = Decimal("0.00")
    for account in accounts:
        balance = _decimal(account.get("balance"))
        total += balance
        kind = str(account.get("account_type") or "account").title()
        status = str(account.get("status") or "unknown")
        lines.append(f"• {kind} account — {_money(balance)} ({status})")
    lines.extend(["", f"Total available balance: {_money(total)}"])
    return "\n".join(lines)


def _render_transactions(observations: list[tuple[str, Any]]) -> str:
    transactions = _records(
        _last_payload(observations, _TOOL_TRANSACTIONS), "transactions"
    )
    if not transactions:
        return "You have no recent transactions."

    lines = ["Recent transactions:", ""]
    for transaction in transactions:
        kind = str(transaction.get("transaction_type") or "transaction")
        status = str(transaction.get("status") or "unknown")
        lines.append(
            f"• {_decimal(transaction.get('amount'))} — {kind}"
            f" — {status} ({_date(transaction.get('timestamp'))})"
        )
    return "\n".join(lines)


def _render_risk(observations: list[tuple[str, Any]]) -> str:
    payload = _last_payload(observations, _TOOL_FRAUD)
    if payload is None:
        transactions = _records(
            _last_payload(observations, _TOOL_TRANSACTIONS), "transactions"
        )
        return _NO_TRANSACTIONS_TEXT if not transactions else _UNAVAILABLE_TEXT

    if not isinstance(payload, dict) or not payload.get("found"):
        return _NO_ASSESSMENT_TEXT

    assessment = payload.get("assessment")
    if not isinstance(assessment, dict) or not assessment:
        return _NO_ASSESSMENT_TEXT

    lines = ["Risk status for your most recent transaction:", ""]
    level = assessment.get("risk_level")
    if level:
        lines.append(f"• Risk level: {str(level).lower()}")
    score = assessment.get("final_score")
    if score is not None:
        lines.append(f"• Final score: {score}")
    reasons = assessment.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines.append("• Signals: " + ", ".join(str(reason) for reason in reasons))
    return "\n".join(lines)


def _newest_transaction_id(observations: list[tuple[str, Any]]) -> str | None:
    """Newest owned transaction id, as already sorted by the transactions tool."""
    transactions = _records(
        _last_payload(observations, _TOOL_TRANSACTIONS), "transactions"
    )
    if not transactions:
        return None
    transaction_id = transactions[0].get("transaction_id")
    return str(transaction_id) if transaction_id else None


def _last_payload(observations: list[tuple[str, Any]], name: str) -> Any:  # noqa: ANN401
    for tool_name, payload in reversed(observations):
        if tool_name == name:
            return payload
    return None


def _records(payload: Any, key: str) -> list[dict[str, Any]]:  # noqa: ANN401
    if not isinstance(payload, dict):
        return []
    records = payload.get(key)
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _is_failure(payload: Any) -> bool:  # noqa: ANN401
    """A tool that errored never produces a specific claim."""
    return isinstance(payload, dict) and bool(payload.get("error"))


def _decimal(value: Any) -> Decimal:  # noqa: ANN401
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _money(amount: Decimal) -> str:
    return f"{amount:,.2f}"


def _date(value: Any) -> str:  # noqa: ANN401
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text


def _tool_call(name: str, arguments: dict[str, Any]) -> LLMResponse:
    return LLMResponse(
        message=LLMMessage(
            role="assistant",
            content=None,
            tool_calls=[
                LLMToolCall(
                    call_id=name,
                    name=name,
                    arguments=json.dumps(arguments),
                )
            ],
        ),
        finish_reason="tool_calls",
    )


def _answer(content: str) -> LLMResponse:
    return LLMResponse(
        message=LLMMessage(role="assistant", content=content),
        finish_reason="stop",
    )
