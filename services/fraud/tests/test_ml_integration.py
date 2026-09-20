"""Phase 12 integration tests: rule + ML combination and failure behavior."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from services.fraud.ml.features import build_feature_row
from services.fraud.ml.model import load_model, predict_probability

from app.domain.risk import CombinedRiskEngine, combine_scores, map_level
from app.domain.rules import RuleEngine


def test_combine_scores_weighted_blend():
    assert combine_scores(0.8, 0.0, 0.6, 0.4) == pytest.approx(0.48)
    assert combine_scores(0.0, 1.0, 0.6, 0.4) == pytest.approx(0.40)
    assert combine_scores(0.8, 0.9, 0.6, 0.4) == pytest.approx(0.84)


def test_combine_scores_rejects_invalid_weights():
    with pytest.raises(ValueError):
        combine_scores(0.5, 0.5, 0.0, 0.0)


def test_map_level_matches_phase10_cutoffs():
    assert map_level(0.0).value == "LOW"
    assert map_level(0.3).value == "MEDIUM"
    assert map_level(0.69).value == "MEDIUM"
    assert map_level(0.7).value == "HIGH"


def test_combined_engine_keeps_rule_signal_and_adds_ml():
    engine = CombinedRiskEngine(load_model())
    assessment = engine.evaluate(
        "event-1", "txn-1", Decimal("15000"), {"transaction_hour": 2}
    )
    # Deterministic rule still fires.
    assert "LARGE_TRANSACTION" in assessment.reasons
    assert assessment.rule_score == pytest.approx(0.8)
    # ML fields are populated and bounded.
    assert assessment.ml_probability is not None
    assert 0.0 <= assessment.ml_probability <= 1.0
    assert assessment.model_version == "fraud-model-v1"
    expected = combine_scores(0.8, assessment.ml_probability, 0.6, 0.4)
    assert assessment.risk_score == pytest.approx(expected)
    assert assessment.risk_level.value == map_level(expected).value


def test_combined_engine_low_risk_transfer_stays_low():
    engine = CombinedRiskEngine(load_model())
    assessment = engine.evaluate("event-2", "txn-2", Decimal("100"), {})
    assert assessment.rule_score == pytest.approx(0.0)
    assert assessment.ml_probability is not None
    # With a tiny amount the combined score cannot cross the HIGH cutoff.
    assert assessment.risk_score < 0.7


def test_combined_engine_flags_high_ml_probability():
    engine = CombinedRiskEngine(load_model())
    # Night-time, brand-new-beneficiary, oversized transfer.
    payload = {
        "transaction_hour": 2,
        "is_new_beneficiary": 1,
        "account_age_days": 30,
        "failed_transaction_count": 3,
    }
    assessment = engine.evaluate("event-3", "txn-3", Decimal("9000"), payload)
    ml_probability = predict_probability(
        engine._model, build_feature_row(payload, 9000.0)
    )
    if ml_probability >= engine._model.metadata.threshold:
        assert "ML_HIGH_RISK" in assessment.reasons
    else:
        assert "ML_HIGH_RISK" not in assessment.reasons


def test_prediction_exception_propagates_for_clear_failure():
    engine = CombinedRiskEngine(load_model())

    class ExplodingPipeline:
        def predict_proba(self, _rows):
            raise RuntimeError("artifact corrupted at runtime")

    with patch.object(engine, "_model") as model:
        model.metadata = load_model().metadata
        model.pipeline = ExplodingPipeline()
        with pytest.raises(RuntimeError, match="corrupted"):
            engine.evaluate("event-4", "txn-4", Decimal("100"), {})


def test_rules_only_engine_unchanged():
    assessment = RuleEngine().evaluate("event-5", "txn-5", Decimal("6000"))
    assert assessment.risk_level.value == "MEDIUM"
    assert assessment.ml_probability is None
    assert assessment.model_version is None
