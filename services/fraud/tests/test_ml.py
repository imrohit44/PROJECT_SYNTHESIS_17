"""Phase 12 ML tests: dataset, features, model artifact, prediction."""

import json

import numpy as np
import pytest
from services.fraud.ml.dataset import (
    FEATURE_COLUMNS,
    RANDOM_SEED,
    TARGET_COLUMN,
    dataset_stats,
    generate_dataset,
)
from services.fraud.ml.features import build_feature_row, feature_vector
from services.fraud.ml.model import (
    DEFAULT_METADATA_PATH,
    DEFAULT_MODEL_PATH,
    FraudModelLoadError,
    load_model,
    predict_probability,
)


def test_dataset_is_reproducible():
    first = generate_dataset(seed=RANDOM_SEED)
    second = generate_dataset(seed=RANDOM_SEED)
    assert first.equals(second)


def test_dataset_class_distribution_is_imbalanced():
    stats = dataset_stats(generate_dataset(seed=RANDOM_SEED))
    assert stats.rows == 5000
    assert 0 < stats.fraud_rate < 0.5
    assert stats.fraud_count == round(stats.rows * stats.fraud_rate)


def test_target_never_appears_in_features():
    assert TARGET_COLUMN not in FEATURE_COLUMNS
    assert set(generate_dataset(seed=RANDOM_SEED).columns) == set(FEATURE_COLUMNS) | {
        TARGET_COLUMN
    }


def test_build_feature_row_is_deterministic():
    raw = {"transaction_hour": 3, "account_age_days": 90}
    a = build_feature_row(raw, amount=250.0)
    b = build_feature_row(raw, amount=250.0)
    assert a == b
    assert list(a.keys()) == FEATURE_COLUMNS


def test_build_feature_row_deviation_is_always_derived():
    row = build_feature_row({"transaction_hour": 9}, amount=100.0)
    assert row["average_transaction_amount"] == pytest.approx(100.0)
    assert row["amount_deviation"] == pytest.approx(
        row["transaction_amount"] / row["average_transaction_amount"]
    )


def test_build_feature_row_handles_malformed_input():
    raw = {"transaction_hour": "not-a-number", "account_age_days": None}
    row = build_feature_row(raw, amount=50.0)
    assert np.isfinite(feature_vector(row)).all()
    assert row["transaction_hour"] == 12.0  # neutral default
    assert row["account_age_days"] == 720.0


def test_model_artifact_loads_with_metadata():
    model = load_model()
    assert model.metadata.model_version == "fraud-model-v1"
    assert model.metadata.threshold == pytest.approx(0.86)
    assert model.metadata.dataset_version == "phase12-v1"
    assert model.metadata.random_seed == RANDOM_SEED
    assert model.metadata.feature_list == FEATURE_COLUMNS
    assert {"precision", "recall", "f1", "roc_auc"} <= set(model.metadata.metrics)
    assert DEFAULT_MODEL_PATH.is_file()
    json.loads(DEFAULT_METADATA_PATH.read_text(encoding="utf-8"))


def test_predict_probability_in_unit_range():
    model = load_model()
    for amount in (10.0, 7500.0, 25000.0):
        probability = predict_probability(model, build_feature_row({}, amount))
        assert 0.0 <= probability <= 1.0


def test_missing_model_artifact_fails_fast(tmp_path):
    with pytest.raises(FraudModelLoadError, match="not found"):
        load_model(model_path=tmp_path / "missing.joblib")


def test_invalid_model_artifact_fails_fast(tmp_path):
    bad = tmp_path / "bad.joblib"
    bad.write_bytes(b"not a model")
    with pytest.raises(FraudModelLoadError):
        load_model(model_path=bad)


def test_model_without_predict_proba_fails_fast(tmp_path):
    import joblib

    artifact = tmp_path / "m.joblib"
    joblib.dump({"not": "a model"}, artifact)
    metadata = tmp_path / "m.metadata.json"
    metadata.write_text(
        json.dumps({"model_version": "x", "feature_list": ["f"]}), encoding="utf-8"
    )
    with pytest.raises(FraudModelLoadError, match="predict_proba"):
        load_model(model_path=artifact, metadata_path=metadata)


def test_metadata_without_feature_list_fails_fast(tmp_path):
    import joblib

    # A real sklearn estimator is picklable and has predict_proba; removing
    # the feature list from the metadata must still fail validation.
    artifact = tmp_path / "m2.joblib"
    joblib.dump(load_model().pipeline, artifact)
    metadata = tmp_path / "m2.metadata.json"
    metadata.write_text(json.dumps({"model_version": "x"}), encoding="utf-8")
    with pytest.raises(FraudModelLoadError, match="feature list"):
        load_model(model_path=artifact, metadata_path=metadata)
