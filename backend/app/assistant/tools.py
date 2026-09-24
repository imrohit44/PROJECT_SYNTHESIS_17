"""Read-only banking assistant tools (Phase 14).

Every executor receives a backend-built ``AgentContext`` (authenticated JWT
principal + existing application services). The LLM never supplies identity,
authorization, or infrastructure values. Executors reuse
``BankApplicationService`` and the Fraud service API instead of duplicating
banking logic, and they are strictly read-only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from .registry import AgentContext, Tool, ToolRegistry
from .schemas import (
    AccountSummaryArgs,
    FraudAssessmentArgs,
    RecentTransactionsArgs,
    TransactionDetailsArgs,
)

# Fields from the Fraud service response that are safe to expose to the
# authenticated owner of the transaction.
_FRAUD_PUBLIC_FIELDS = (
    "risk_level",
    "risk_score",
    "rule_score",
    "ml_probability",
    "combined_score",
    "graph_score",
    "graph_adjustment",
    "final_score",
    "reasons",
    "model_version",
    "graph_version",
    "graph_signals",
)


class ToolExecutionError(Exception):
    """Raised when a tool cannot produce data (never leaks infrastructure)."""


def _owned_account_ids(context: AgentContext) -> list[str]:
    """Account ids owned by the authenticated customer (admin included)."""
    accounts = context.bank.list_accounts(context.user.customer_id)
    return [account.account_id for account in accounts]


def _assert_account_access(context: AgentContext, account_id: str) -> None:
    """Backend authorization: only the owner (or an admin) may proceed."""
    from backend.app.security.roles import UserRole

    if context.user.role is UserRole.ADMIN:
        return
    if context.bank.account_owner_id(account_id) != context.user.customer_id:
        raise ToolExecutionError("Account not found")


def _account_summary(context: AgentContext, account_id: str) -> dict[str, Any]:
    account = context.bank.find_account(account_id)
    return {
        "account_id": account.account_id,
        "account_type": (
            "savings" if account.__class__.__name__ == "SavingsAccount" else "current"
        ),
        "balance": f"{account.balance:.2f}",
        "status": account.status,
    }


def get_account_summary(
    args: AccountSummaryArgs, context: AgentContext
) -> dict[str, Any]:
    """Summaries of the authenticated customer's own accounts."""
    return {
        "accounts": [
            _account_summary(context, account_id)
            for account_id in _owned_account_ids(context)
        ]
    }


def get_recent_transactions(
    args: RecentTransactionsArgs, context: AgentContext
) -> dict[str, Any]:
    """Most recent transactions across the customer's own accounts."""
    transactions: list[dict[str, Any]] = []
    for account_id in _owned_account_ids(context):
        for item in context.bank.list_transactions(account_id):
            transactions.append(
                {
                    "transaction_id": item.transaction_id,
                    "transaction_type": item.transaction_type,
                    "amount": f"{Decimal(item.amount):.2f}",
                    "timestamp": item.timestamp.isoformat(),
                    "status": item.status,
                    "account_id": account_id,
                }
            )
    transactions.sort(key=lambda entry: entry["timestamp"], reverse=True)
    return {"transactions": transactions[: args.limit], "total": len(transactions)}


def _find_transaction(
    context: AgentContext, transaction_id: str
) -> dict[str, Any] | None:
    """Locate a transaction across the authenticated user's own accounts."""
    for account_id in _owned_account_ids(context):
        for item in context.bank.list_transactions(account_id):
            if item.transaction_id == transaction_id:
                return {
                    "transaction_id": item.transaction_id,
                    "transaction_type": item.transaction_type,
                    "amount": f"{Decimal(item.amount):.2f}",
                    "timestamp": item.timestamp.isoformat(),
                    "status": item.status,
                    "source_account_id": item.source_account_id,
                    "destination_account_id": item.destination_account_id,
                }
    return None


def get_transaction_details(
    args: TransactionDetailsArgs, context: AgentContext
) -> dict[str, Any]:
    """Details of one transaction, only if it belongs to the caller."""
    details = _find_transaction(context, args.transaction_id)
    if details is None:
        return {"found": False}
    return {"found": True, "transaction": details}


def get_fraud_assessment(
    args: FraudAssessmentArgs, context: AgentContext
) -> dict[str, Any]:
    """Risk assessment for one owned transaction, from the Fraud service."""
    if _find_transaction(context, args.transaction_id) is None:
        return {"found": False}

    try:
        response = httpx.get(
            f"{context.fraud_service_url}/api/v1/risk-assessments/{args.transaction_id}",
            timeout=context.timeout,
        )
    except httpx.HTTPError:
        raise ToolExecutionError("Risk assessment is currently unavailable") from None
    if response.status_code == 404:
        return {"found": False}
    if response.status_code != 200:
        raise ToolExecutionError("Risk assessment is currently unavailable")

    payload: dict[str, Any] = response.json()
    return {
        "found": True,
        "assessment": {field: payload.get(field) for field in _FRAUD_PUBLIC_FIELDS},
    }


def build_tool_registry() -> ToolRegistry:
    """Build the explicit, allowlist-only tool registry for the assistant."""
    tools = [
        Tool(
            name="get_account_summary",
            description=("Retrieve the authenticated user's own account balances."),
            args_model=AccountSummaryArgs,
            executor=get_account_summary,
        ),
        Tool(
            name="get_recent_transactions",
            description="Recent transactions for your own accounts.",
            args_model=RecentTransactionsArgs,
            executor=get_recent_transactions,
        ),
        Tool(
            name="get_transaction_details",
            description="Details of a transaction you own.",
            args_model=TransactionDetailsArgs,
            executor=get_transaction_details,
        ),
        Tool(
            name="get_fraud_assessment",
            description=("Fraud risk assessment for a transaction you own."),
            args_model=FraudAssessmentArgs,
            executor=get_fraud_assessment,
        ),
    ]
    return ToolRegistry(tools)
