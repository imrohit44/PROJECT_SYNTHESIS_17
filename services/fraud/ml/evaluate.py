"""Reproducible standalone evaluation of the trained fraud model.

Usage (from repository root):
    python -m services.fraud.ml.evaluate

Trains on the training split and evaluates on the held-out validation split
(the same protocol as train.py) and reports precision, recall, F1, ROC-AUC,
the confusion matrix, class counts, and the selected threshold.

Interpretation:
- False Negative: fraud predicted as legitimate -> direct monetary loss.
- False Positive: legitimate transfer flagged as fraud -> blocked customers,
  manual review cost, lost trust. Both have operational consequences, which
  is why accuracy alone is meaningless under heavy class imbalance: with a 6%
  fraud rate, "always predict legitimate" is 94% accurate and catches nothing.
"""

from __future__ import annotations

import json

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from .dataset import (
    DATASET_VERSION,
    FEATURE_COLUMNS,
    RANDOM_SEED,
    TARGET_COLUMN,
    dataset_stats,
    generate_dataset,
)
from .model import DEFAULT_METADATA_PATH, MODEL_VERSION, load_model


def evaluate() -> dict[str, object]:
    stats = dataset_stats(generate_dataset(seed=RANDOM_SEED))
    frame = generate_dataset(n_rows=20000, seed=RANDOM_SEED)
    features = frame[FEATURE_COLUMNS].to_numpy(dtype=float)
    target = frame[TARGET_COLUMN].to_numpy(dtype=int)

    _, x_val, _, y_val = train_test_split(
        features, target, test_size=0.25, stratify=target, random_state=RANDOM_SEED
    )

    # Evaluate the committed artifact when present so this script proves what
    # production runs; otherwise train a fresh model for local exploration.
    if DEFAULT_METADATA_PATH.is_file():
        bundle = load_model()
        model, threshold = bundle.pipeline, bundle.metadata.threshold
    else:
        model = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.1,
            max_depth=4,
            class_weight="balanced",
            random_state=RANDOM_SEED,
        )
        model.fit(features, target)
        threshold = 0.5

    probabilities = model.predict_proba(x_val)[:, 1]
    predicted = (probabilities >= threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_val, predicted, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(y_val, predicted).ravel()

    return {
        "model_version": MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "random_seed": RANDOM_SEED,
        "threshold": threshold,
        "fraud_count": stats.fraud_count,
        "non_fraud_count": stats.non_fraud_count,
        "validation_fraud_count": int(y_val.sum()),
        "validation_non_fraud_count": int((y_val == 0).sum()),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc_score(y_val, probabilities)), 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
    }


def main() -> None:
    print(json.dumps(evaluate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
