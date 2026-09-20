"""Train and evaluate the Phase 12 fraud model (reproducible, fixed seed).

Usage (from repository root):
    python -m services.fraud.ml.train

Produces:
    services/fraud/models/fraud_model.joblib
    services/fraud/models/fraud_model.metadata.json

Strategy:
- stratified train/validation split (fraud is the minority class)
- class weighting instead of synthetic oversampling
- threshold chosen on the VALIDATION set by maximizing F1 (never assumed 0.5)
- target column is_fraud is never passed to the model as a feature
"""

from __future__ import annotations

import json

import numpy as np
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
    generate_dataset,
)
from .model import MODEL_VERSION, save_model, utc_now_iso


def train_model(n_rows: int = 20000, fraud_rate: float = 0.06):
    """Train the model and return (pipeline, metrics dict, threshold)."""
    frame = generate_dataset(n_rows=n_rows, fraud_rate=fraud_rate, seed=RANDOM_SEED)
    features = frame[FEATURE_COLUMNS].to_numpy(dtype=float)
    target = frame[TARGET_COLUMN].to_numpy(dtype=int)

    x_train, x_val, y_train, y_val = train_test_split(
        features,
        target,
        test_size=0.25,
        stratify=target,
        random_state=RANDOM_SEED,
    )

    model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        max_depth=4,
        class_weight="balanced",
        random_state=RANDOM_SEED,
    )
    model.fit(x_train, y_train)

    probabilities = model.predict_proba(x_val)[:, 1]

    # Threshold search on the validation set: maximize F1, tie-break toward
    # higher recall because missed fraud (false negatives) costs more.
    thresholds = np.linspace(0.05, 0.95, 91)
    best_threshold, best_f1 = 0.5, -1.0
    for candidate in thresholds:
        predicted = (probabilities >= candidate).astype(int)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_val, predicted, average="binary", zero_division=0
        )
        score = (f1, recall)
        if score > (best_f1, -1.0):
            best_threshold, best_f1 = float(candidate), float(f1)

    predicted = (probabilities >= best_threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_val, predicted, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(y_val, predicted).ravel()
    metrics = {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc_score(y_val, probabilities)), 4),
        "accuracy": round(float((tp + tn) / (tp + tn + fp + fn)), 4),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
        "validation_rows": int(len(y_val)),
        "validation_fraud_count": int(y_val.sum()),
        "validation_non_fraud_count": int((y_val == 0).sum()),
    }
    return model, metrics, best_threshold


def main() -> None:
    model, metrics, threshold = train_model()
    metadata = {
        "model_version": MODEL_VERSION,
        "trained_at": utc_now_iso(),
        "threshold": round(threshold, 2),
        "dataset_version": DATASET_VERSION,
        "random_seed": RANDOM_SEED,
        "feature_list": FEATURE_COLUMNS,
        "metrics": metrics,
    }
    save_model(model, metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
