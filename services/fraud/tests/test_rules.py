from decimal import Decimal

from app.domain.models import RiskLevel
from app.domain.rules import RuleEngine


def test_rule_engine_large_transaction():
    engine = RuleEngine()
    assessment = engine.evaluate("event-1", "txn-1", Decimal("15000"))

    assert assessment.risk_level == RiskLevel.HIGH
    assert assessment.risk_score == 0.8
    assert "LARGE_TRANSACTION" in assessment.reasons


def test_rule_engine_medium_transaction():
    engine = RuleEngine()
    assessment = engine.evaluate("event-2", "txn-2", Decimal("6000"))

    assert assessment.risk_level == RiskLevel.MEDIUM
    assert assessment.risk_score == 0.4
    assert "MEDIUM_TRANSACTION" in assessment.reasons


def test_rule_engine_low_transaction():
    engine = RuleEngine()
    assessment = engine.evaluate("event-3", "txn-3", Decimal("1000"))

    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.risk_score == 0.0
    assert len(assessment.reasons) == 0
