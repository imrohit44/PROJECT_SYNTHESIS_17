"""Combined risk scoring: deterministic rules + ML probability.

The deterministic rule score stays the foundation; the ML model contributes an
additional, weighted probability signal. The combination is a transparent
linear blend with configurable weights:

    combined_score = rule_weight * rule_score + ml_weight * ml_probability

Risk levels use the same cutoffs the Phase 10 rules always used:
>= 0.7 HIGH, >= 0.3 MEDIUM, otherwise LOW. The ML model can therefore raise or
lower a score but can never silently bypass a deterministic rule.
"""

from __future__ import annotations

from decimal import Decimal

from services.fraud.ml.features import build_feature_row
from services.fraud.ml.model import FraudModel, predict_probability

from .models import RiskAssessment, RiskLevel
from .rules import RuleEngine

HIGH_RISK_CUTOFF = 0.7
MEDIUM_RISK_CUTOFF = 0.3


def combine_scores(
    rule_score: float, ml_probability: float, rule_weight: float, ml_weight: float
) -> float:
    """Weighted linear blend of the rule score and the ML probability."""
    total_weight = rule_weight + ml_weight
    if total_weight <= 0:
        raise ValueError("rule_weight and ml_weight must be positive")
    combined = (rule_weight * rule_score + ml_weight * ml_probability) / total_weight
    return min(max(combined, 0.0), 1.0)


def map_level(combined_score: float) -> RiskLevel:
    """Map a combined score to the same levels the rules have always used."""
    if combined_score >= HIGH_RISK_CUTOFF:
        return RiskLevel.HIGH
    if combined_score >= MEDIUM_RISK_CUTOFF:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class CombinedRiskEngine:
    """Evaluates deterministic rules, then adds the ML probability signal."""

    def __init__(
        self,
        model: FraudModel,
        rule_weight: float = 0.6,
        ml_weight: float = 0.4,
    ) -> None:
        if rule_weight <= 0 or ml_weight <= 0:
            raise ValueError("rule_weight and ml_weight must be positive")
        self._rules = RuleEngine()
        self._model = model
        self._rule_weight = rule_weight
        self._ml_weight = ml_weight

    @property
    def model_version(self) -> str:
        return self._model.metadata.model_version

    def evaluate(
        self,
        event_id: str,
        transaction_id: str,
        amount: Decimal,
        payload: dict[str, object],
    ) -> RiskAssessment:
        """Run rules + ML. Raises on prediction failure (caller decides)."""
        rule_assessment = self._rules.evaluate(event_id, transaction_id, amount)

        feature_row = build_feature_row(dict(payload), float(amount))
        ml_probability = predict_probability(self._model, feature_row)

        combined = combine_scores(
            rule_assessment.risk_score,
            ml_probability,
            self._rule_weight,
            self._ml_weight,
        )
        reasons = list(rule_assessment.reasons)
        if ml_probability >= self._model.metadata.threshold:
            reasons.append("ML_HIGH_RISK")

        return RiskAssessment(
            event_id=event_id,
            transaction_id=transaction_id,
            risk_score=combined,
            risk_level=map_level(combined),
            reasons=reasons,
            rule_score=rule_assessment.risk_score,
            ml_probability=ml_probability,
            model_version=self.model_version,
        )
