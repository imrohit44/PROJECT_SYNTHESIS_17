"""Deterministic synthetic fraud dataset for Phase 12 learning.

The data is intentionally synthetic: no real customer data is used. A fixed
random seed makes generation reproducible. Fraud is the minority class and is
not separable by any single obvious feature.

is_fraud is the target and is never included as an input feature.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS as FEATURE_COLUMNS

DATASET_VERSION = "phase12-v1"
RANDOM_SEED = 42

# The feature contract lives in features.py (the shared training/runtime
# layer); re-exported here for training and evaluation convenience.

TARGET_COLUMN = "is_fraud"

FEATURE_MEANINGS = {
    "transaction_amount": "Transfer amount in synthetic currency units.",
    "transaction_hour": "Hour of day the transfer was initiated (0-23).",
    "transaction_day": "Day of week the transfer was initiated (0=Monday).",
    "account_age_days": "Age of the source account in days.",
    "transaction_frequency": "Transfers from the source account in prior 7 days.",
    "average_transaction_amount": "Mean prior transfer amount for the account.",
    "amount_deviation": "amount / max(average amount, 1); spending surprise.",
    "failed_transaction_count": "Failed attempts on the account in prior 7 days.",
    "beneficiary_frequency": "Prior transfers to the same destination account.",
    "account_balance_before": "Source balance before the transfer.",
    "account_balance_after": "Source balance after the transfer.",
    "is_new_beneficiary": "1 when destination has never been used before.",
}


@dataclass(frozen=True)
class DatasetStats:
    rows: int
    fraud_count: int
    non_fraud_count: int
    fraud_rate: float


def generate_dataset(
    n_rows: int = 5000,
    fraud_rate: float = 0.06,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    is_fraud = rng.random(n_rows) < fraud_rate

    hour = rng.integers(0, 24, n_rows).astype(float)
    # Fraud is more common at night, but night traffic is mostly legitimate.
    hour = np.where(
        is_fraud & (rng.random(n_rows) < 0.55),
        rng.integers(0, 5, n_rows).astype(float),
        hour,
    )
    day = rng.integers(0, 7, n_rows).astype(float)
    account_age = np.clip(rng.normal(720, 420, n_rows), 7, 4000)
    # Newer accounts carry slightly more fraud risk, with heavy overlap.
    account_age = np.where(is_fraud, np.clip(account_age * 0.55, 7, 4000), account_age)
    frequency = rng.poisson(2.2, n_rows).astype(float)
    frequency = np.where(
        is_fraud & (rng.random(n_rows) < 0.4),
        frequency + rng.integers(3, 8, n_rows),
        frequency,
    )
    average_amount = np.clip(rng.lognormal(5.4, 0.9, n_rows), 20, 20000)
    amount = np.clip(
        rng.lognormal(5.2, 1.0, n_rows) * np.where(is_fraud, 1.9, 1.0), 5, 30000
    )
    deviation = amount / np.maximum(average_amount, 1.0)
    failed = rng.poisson(0.25, n_rows).astype(float)
    failed = np.where(
        is_fraud & (rng.random(n_rows) < 0.35),
        failed + rng.integers(1, 4, n_rows),
        failed,
    )
    beneficiary_frequency = rng.poisson(3.0, n_rows).astype(float)
    is_new = (rng.random(n_rows) < 0.25).astype(float)
    # Fraud more often targets a new beneficiary, but most new-beneficiary
    # transfers are legitimate.
    is_new = np.where(is_fraud & (rng.random(n_rows) < 0.6), 1.0, is_new)
    beneficiary_frequency = np.where(is_new == 1.0, 0.0, beneficiary_frequency)
    balance_before = np.clip(rng.lognormal(8.2, 1.0, n_rows), 100, 200000)
    balance_after = np.maximum(balance_before - amount, 0.0)

    return pd.DataFrame(
        {
            "transaction_amount": amount,
            "transaction_hour": hour,
            "transaction_day": day,
            "account_age_days": account_age,
            "transaction_frequency": frequency,
            "average_transaction_amount": average_amount,
            "amount_deviation": deviation,
            "failed_transaction_count": failed,
            "beneficiary_frequency": beneficiary_frequency,
            "account_balance_before": balance_before,
            "account_balance_after": balance_after,
            "is_new_beneficiary": is_new,
            TARGET_COLUMN: is_fraud.astype(int),
        }
    )


def dataset_stats(frame: pd.DataFrame) -> DatasetStats:
    fraud_count = int(frame[TARGET_COLUMN].sum())
    rows = int(len(frame))
    return DatasetStats(
        rows=rows,
        fraud_count=fraud_count,
        non_fraud_count=rows - fraud_count,
        fraud_rate=(fraud_count / rows) if rows else 0.0,
    )
