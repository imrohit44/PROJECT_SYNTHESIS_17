# Phase 12 — ML-Based Fraud Detection

## Overview

Phase 12 adds a machine-learning risk signal to the existing deterministic Fraud
service. Phase 11 remains the stable baseline; the Kafka contract
(`pybank.events`, `transfer.completed`, `risk.assessed`), the outbox pattern and
all observability are unchanged.

## Runtime flow

```
transfer.completed (Kafka)
        ↓
Fraud consumer (idempotency check)
        ↓
feature extraction (services/fraud/ml/features.py)
        ↓
┌──────────────────────────────┐
│ Deterministic rules (Phase 10)│
│            +                  │
│ ML model (fraud-model-v1)     │
└──────────────┬───────────────┘
               ↓
   combined_score = 0.6 * rule_score + 0.4 * ml_probability
               ↓
   LOW / MEDIUM / HIGH (same cutoffs: 0.3 / 0.7)
               ↓
   fraud_assessments + outbox → risk.assessed
```

## Components

| Component | Location | Purpose |
|---|---|---|
| Dataset generator | `services/fraud/ml/dataset.py` | Deterministic synthetic dataset (seed 42, 5 000 rows, ~8% fraud) |
| Feature layer | `services/fraud/ml/features.py` | Single source of the 12-feature contract, used at training AND runtime |
| Training | `services/fraud/ml/train.py` | Trains GradientBoosting, writes artifact + metadata |
| Evaluation | `services/fraud/ml/evaluate.py` | Precision / recall / F1 / ROC-AUC / confusion matrix |
| Model wrapper | `services/fraud/ml/model.py` | Strict artifact loading with fail-fast validation |
| Combined engine | `services/fraud/app/domain/risk.py` | Transparent rule + ML blend |
| Migration | `services/fraud/alembic/versions/c4d5e6f7a8b9_add_ml_scoring_columns.py` | Additive nullable columns |

## Model artifact

- `services/fraud/models/fraud_model.joblib` — sklearn `GradientBoostingClassifier`
  in a `StandardScaler + classifier` pipeline (~150 KB, committed so the service runs).
- `services/fraud/models/fraud_model.metadata.json` — model version
  (`fraud-model-v1`), training date, feature list, threshold (0.86),
  evaluation metrics, dataset version and seed.
- Regenerate: `python -m services.fraud.ml.train` then
  `python -m services.fraud.ml.evaluate` (requires the `ml` optional
  dependency group for pandas).

## Threshold selection

0.86 was chosen on the validation set as the probability at which precision is
maximised while recall stays usable. With 0.5 the model produced too many
false positives on legitimate large-but-normal transfers; 0.86 means the ML
signal only escalates risk when it is genuinely confident. The value is stored
in the metadata and surfaced in `fraud_service_started` logs.

## Failure behavior

- Missing/invalid artifact → service fails to start (no silent "ML disabled").
- Prediction exception → assessment fails clearly, `fraud_ml_predictions_total{outcome="failure"}`
  increments, no assessment row is written, Banking is unaffected.
- Malformed feature input → neutral defaults, never NaN/Inf.

## Deliberately out of scope (future improvements)

Optuna, MLflow, model registry, feature store, separate ML service,
automated retraining, deep learning, Kubernetes.
