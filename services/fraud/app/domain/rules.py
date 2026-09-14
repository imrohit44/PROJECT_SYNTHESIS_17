from decimal import Decimal

from .models import RiskAssessment, RiskLevel


class RuleEngine:
    def evaluate(
        self, event_id: str, transaction_id: str, amount: Decimal
    ) -> RiskAssessment:
        score = 0.0
        reasons: list[str] = []

        if amount > Decimal("10000"):
            score += 0.8
            reasons.append("LARGE_TRANSACTION")
        elif amount > Decimal("5000"):
            score += 0.4
            reasons.append("MEDIUM_TRANSACTION")

        if score >= 0.7:
            level = RiskLevel.HIGH
        elif score >= 0.3:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return RiskAssessment(
            event_id=event_id,
            transaction_id=transaction_id,
            risk_score=min(score, 1.0),
            risk_level=level,
            reasons=reasons,
        )
