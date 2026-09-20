# Phase 12 Learning Notes — ML Fraud Detection

## 1. Why fraud detection needs ML

Deterministic rules are explicit thresholds ("amount > 10 000 → risky"). They
are explainable but rigid: fraudsters stay just under the thresholds, and rules
cannot capture interactions (a small amount at 3 a.m. to a brand-new
beneficiary is more suspicious than the same amount at noon to a known payee).
An ML model learns those interactions from labelled examples.

## 2. Why deterministic rules are retained

Rules encode business and regulatory knowledge and are instantly auditable.
The ML model is an *additional* signal, blended as
`0.6 * rule_score + 0.4 * ml_probability`. ML can raise the combined score but
can never remove a rule-based signal — if `LARGE_TRANSACTION` fires, the rule
contribution of 0.8 stays in the score and the reason list.

## 3. How features are created

One module (`ml/features.py`) owns the 12-feature contract. Training builds
rows with the same `build_feature_row()` the runtime consumer calls on each
Kafka event. Deviating features (e.g. a runtime-supplied average) are ignored
in favour of derived values, so training and serving can never drift apart.

## 4. What the model predicts

`predict_proba` → the probability (0.0–1.0) that a transfer is fraudulent,
given the transaction's features. It is a GradientBoostingClassifier trained on
a synthetic, seeded dataset.

## 5. Why probability (not a yes/no label)

A probability lets the risk engine weigh the ML signal instead of letting it
overrule everything, and it allows one documented threshold to be tuned without
retraining. Hard labels would hide how confident the model is.

## 6. Why precision/recall/F1 matter

With ~8% fraud, a model predicting "legitimate" for everything scores ~92%
accuracy while catching zero fraud. Precision (of flagged, how many were truly
fraud) and recall (of true fraud, how many were caught) are the metrics that
describe real behaviour; F1 balances them, ROC-AUC measures ranking quality
independently of the threshold.

## 7. False positives and false negatives

- **False negative** — fraud passes as legitimate: direct money loss.
- **False positive** — a legitimate transfer is flagged: customer friction,
  manual review cost, loss of trust.
Both have operational consequences; the threshold (0.86) trades recall for
precision because wrongly blocking honest customers is expensive too.

## 8. How ML integrates into the Fraud microservice

The model is loaded **once** at Fraud startup and injected into the consumer.
Each `transfer.completed` goes: features → rules → ML → blend → assessment →
outbox → `risk.assessed`. No new service, no new topic.

## 9. Why the model is loaded once

Deserialising a joblib artifact costs tens of milliseconds plus memory
allocation. Doing it per event would multiply Kafka lag for no benefit and
introduce a failure mode on every message instead of once at startup. A bad
artifact then fails the service fast at boot rather than per-event at runtime.

## 10. Limitations of synthetic training data

The dataset is generated with a fixed seed and hand-designed fraud patterns.
Its metrics say nothing about real-world performance: real fraud is adversarial,
non-stationary and far subtler. The numbers demonstrate the *pipeline*
(lifecycle, evaluation, integration), not production accuracy.
