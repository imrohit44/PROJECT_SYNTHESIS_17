"""Shared feature engineering for the Phase 12 fraud model.

The SAME transformation is used at training time and at runtime prediction
time, which prevents train/serve feature skew. Raw inputs (the synthetic
dataset rows during training, the transfer.completed payload at runtime) are
normalized into the fixed FEATURE_COLUMNS vector defined in dataset.py.

Runtime aggregates the Fraud service cannot compute from a single Kafka event
(account age, 7-day frequency, historical average amount, failed attempts,
beneficiary history, balances) fall back to documented neutral defaults. This
keeps the feature contract identical while being honest about what a stateless
consumer knows.
"""

from __future__ import annotations

from typing import Any

# The canonical model feature contract. Defined here (the shared
# training/runtime layer); dataset.py re-exports it for training use so the
# runtime prediction path never needs pandas.
FEATURE_COLUMNS = [
    "transaction_amount",
    "transaction_hour",
    "transaction_day",
    "account_age_days",
    "transaction_frequency",
    "average_transaction_amount",
    "amount_deviation",
    "failed_transaction_count",
    "beneficiary_frequency",
    "account_balance_before",
    "account_balance_after",
    "is_new_beneficiary",
]

# Neutral, documented runtime defaults for aggregates unavailable in a single
# transfer.completed event. They correspond to the dataset's "typical
# legitimate" profile so the model is not biased toward HIGH at runtime.
RUNTIME_DEFAULTS: dict[str, float] = {
    "transaction_hour": 12.0,
    "transaction_day": 2.0,
    "account_age_days": 720.0,
    "transaction_frequency": 2.2,
    "average_transaction_amount": 0.0,  # replaced by the current amount
    "failed_transaction_count": 0.0,
    "beneficiary_frequency": 3.0,
    "account_balance_before": 0.0,
    "account_balance_after": 0.0,
    "is_new_beneficiary": 0.0,
}


def _as_float(value: Any, default: float) -> float:
    """Convert a raw JSON value to float, falling back on any malformation."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_feature_row(raw: dict[str, Any], amount: float) -> dict[str, float]:
    """Deterministically map raw inputs to the model's feature vector.

    ``amount`` is the transaction amount already parsed by the caller (the
    Fraud consumer parses it as Decimal for the rules). Every output is a
    finite float in FEATURE_COLUMNS order; nothing here depends on the target.
    """
    defaults = dict(RUNTIME_DEFAULTS)
    defaults["average_transaction_amount"] = amount if amount > 0 else 1.0

    hour = _as_float(raw.get("transaction_hour"), defaults["transaction_hour"])
    day = _as_float(raw.get("transaction_day"), defaults["transaction_day"])

    row = {
        "transaction_amount": max(amount, 0.0),
        "transaction_hour": hour % 24.0,
        "transaction_day": day % 7.0,
        "account_age_days": max(
            _as_float(raw.get("account_age_days"), defaults["account_age_days"]), 0.0
        ),
        "transaction_frequency": max(
            _as_float(
                raw.get("transaction_frequency"), defaults["transaction_frequency"]
            ),
            0.0,
        ),
        "average_transaction_amount": max(
            _as_float(
                raw.get("average_transaction_amount"),
                defaults["average_transaction_amount"],
            ),
            0.0,
        ),
        "failed_transaction_count": max(
            _as_float(
                raw.get("failed_transaction_count"),
                defaults["failed_transaction_count"],
            ),
            0.0,
        ),
        "beneficiary_frequency": max(
            _as_float(
                raw.get("beneficiary_frequency"), defaults["beneficiary_frequency"]
            ),
            0.0,
        ),
        "account_balance_before": max(
            _as_float(
                raw.get("account_balance_before"), defaults["account_balance_before"]
            ),
            0.0,
        ),
        "account_balance_after": max(
            _as_float(
                raw.get("account_balance_after"), defaults["account_balance_after"]
            ),
            0.0,
        ),
        "is_new_beneficiary": 1.0
        if _as_float(raw.get("is_new_beneficiary"), defaults["is_new_beneficiary"])
        >= 0.5
        else 0.0,
    }

    # amount_deviation is always derived, never trusted from the input, so it
    # cannot disagree with the two features it depends on.
    row["average_transaction_amount"] = max(row["average_transaction_amount"], 1.0)
    row["amount_deviation"] = (
        row["transaction_amount"] / row["average_transaction_amount"]
    )
    return {column: float(row[column]) for column in FEATURE_COLUMNS}


def feature_vector(row: dict[str, float]) -> list[float]:
    """Ordered feature values in FEATURE_COLUMNS order."""
    return [row[column] for column in FEATURE_COLUMNS]
