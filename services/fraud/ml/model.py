"""Fraud model artifact loading and prediction.

The model is loaded ONCE at Fraud service startup (fail fast on a missing or
invalid artifact) and reused for every Kafka event. Predictions return a
probability in [0.0, 1.0].
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from .features import feature_vector

MODEL_VERSION = "fraud-model-v1"
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent / "models" / "fraud_model.joblib"
)
DEFAULT_METADATA_PATH = DEFAULT_MODEL_PATH.with_suffix(".metadata.json")


class FraudModelLoadError(RuntimeError):
    """Raised when the model artifact is missing or invalid."""


@dataclass(frozen=True)
class ModelMetadata:
    model_version: str
    trained_at: str
    threshold: float
    dataset_version: str
    random_seed: int
    metrics: dict[str, float]
    feature_list: list[str]


@dataclass(frozen=True)
class FraudModel:
    pipeline: Any
    metadata: ModelMetadata


def load_model(
    model_path: Path = DEFAULT_MODEL_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> FraudModel:
    """Load and validate the model artifact and its metadata.

    Fails fast: a missing or corrupt artifact is a startup error, never a
    silent "ML disabled" state.
    """
    if not model_path.is_file():
        raise FraudModelLoadError(f"Model artifact not found: {model_path}")
    if not metadata_path.is_file():
        raise FraudModelLoadError(f"Model metadata not found: {metadata_path}")

    try:
        pipeline = joblib.load(model_path)
        raw: dict[str, Any] = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as error:  # joblib/json raise assorted exception types
        raise FraudModelLoadError(f"Invalid model artifact: {error}") from error

    if not hasattr(pipeline, "predict_proba"):
        raise FraudModelLoadError("Model artifact has no predict_proba method")

    metadata = ModelMetadata(
        model_version=str(raw.get("model_version", "unknown")),
        trained_at=str(raw.get("trained_at", "unknown")),
        threshold=float(raw.get("threshold", 0.5)),
        dataset_version=str(raw.get("dataset_version", "unknown")),
        random_seed=int(raw.get("random_seed", 0)),
        metrics={str(k): float(v) for k, v in raw.get("metrics", {}).items()},
        feature_list=list(raw.get("feature_list", [])),
    )
    if metadata.feature_list == []:
        raise FraudModelLoadError("Model metadata is missing the feature list")
    return FraudModel(pipeline=pipeline, metadata=metadata)


def predict_probability(model: FraudModel, feature_row: dict[str, float]) -> float:
    """Return the fraud probability for one feature row, clamped to [0, 1]."""
    probabilities = model.pipeline.predict_proba([feature_vector(feature_row)])
    probability = float(probabilities[0][1])
    return min(max(probability, 0.0), 1.0)


def save_model(
    pipeline: Any,
    metadata: dict[str, Any],
    model_path: Path = DEFAULT_MODEL_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> None:
    """Persist the model and metadata (used by the training script)."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
