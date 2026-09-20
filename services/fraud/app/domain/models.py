from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class RiskAssessment:
    event_id: str
    transaction_id: str
    risk_score: float
    risk_level: RiskLevel
    reasons: list[str]
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Phase 12 ML fields. None means "assessed by rules only".
    rule_score: float | None = None
    ml_probability: float | None = None
    model_version: str | None = None
