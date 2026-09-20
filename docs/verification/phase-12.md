# Phase 12 Verification — ML Fraud Detection

All evidence below was captured at runtime on 2026-09-20 against the running
Docker stack (no volume wipes; Phase 10/11 data preserved).

## 1. Dataset & training

| Requirement | Test | Result | Evidence |
|---|---|---|---|
| Reproducible generation | `python -m services.fraud.ml.train` (twice) | PASS | Identical metrics both runs (seed 42) |
| Class imbalance | dataset stats | PASS | 5 000 rows, 8% fraud |
| No leakage | `test_target_never_appears_in_features` | PASS | `is_fraud` excluded from 12-feature contract |

## 2. Evaluation metrics (validation set, threshold 0.86)

| Metric | Value |
|---|---|
| Precision | 0.7143 |
| Recall | 0.5941 |
| F1 | 0.6486 |
| ROC-AUC | 0.9494 |
| Confusion matrix | TP 180, FP 72, FN 123, TN 4 625 |
| Fraud / non-fraud (test) | 294 / 4 706 |

## 3. Runtime integration (real event path)

| Requirement | Test | Result | Evidence |
|---|---|---|---|
| Model loaded once, fail-fast | Fraud startup log | PASS | `fraud_service_started … model_version=fraud-model-v1, ml_threshold=0.86` |
| Real transfer → ML prediction | `artifacts/phase12/verify_e2e_ml.py` | PASS `E2E_ML_OK: true` | LARGE txn: rule 0.8, ml 0.0828, combined 0.5131 → MEDIUM; `E2E_ML_OK` |
| Assessment stores ML result | fraud DB + API | PASS | `ml_probability`, `combined_score`, `model_version='fraud-model-v1'` persisted |
| Correlation preserved | end-to-end | PASS | `phase12-final-test-d7d28f22` identical in response, Kafka and `risk.assessed` |

## 4. Deterministic rule regression

| Requirement | Test | Result | Evidence |
|---|---|---|---|
| LARGE_TRANSACTION still fires | E2E scenario 1 | PASS | reason `LARGE_TRANSACTION`, rule_score 0.8 in assessment |
| MEDIUM_TRANSACTION still fires | E2E scenario 2 | PASS | reason `MEDIUM_TRANSACTION`, rule_score 0.4 |

## 5. Idempotency regression

Replayed event `3472b69f-560e-4f1b-a8a6-01f862bc9fd2` on `pybank.events`:

- `fraud_events_consumed_total` 3.0 → 4.0 (replay consumed)
- `fraud_duplicate_events_total` 1.0 → 2.0 (duplicate detected)
- `fraud_assessments` rows for the event: **1** (unchanged)
- `processed_events` rows: **1** (unchanged)

## 6. ML metrics (bounded labels)

```
fraud_ml_predictions_total{outcome="success"} 2.0
fraud_ml_high_risk_total 0.0
```

No transaction/customer/event/correlation identifiers are used as labels.

## 7. Quality gates

| Gate | Result |
|---|---|
| Fraud pytest | 23 passed |
| Backend pytest | 61 passed, 3 skipped |
| ruff check / format | All checks passed, 133 files formatted |
| mypy (backend 77 / fraud 13 files) | Success |
| Frontend test/lint/typecheck/build | PASS (unchanged in Phase 12) |

## 8. Docker

`docker compose build fraud` succeeded (ML deps + model artifact baked in);
`docker compose up -d fraud` → container healthy, migration
`c4d5e6f7a8b9_add_ml_scoring_columns` applied additively.

## Verdict

🟢 COMPLETE — the trained model is genuinely exercised through the real
Kafka → Fraud → DB path; rules, idempotency and observability regressions pass.
