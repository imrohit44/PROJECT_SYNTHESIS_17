"""Add ML scoring columns to fraud_assessments.

Revision ID: c4d5e6f7a8b9
Revises: a1b2c3d4e5f6

All columns are additive and nullable so existing Phase 10/11 assessments and
the Phase 11 Kafka contract remain fully valid.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fraud_assessments", sa.Column("rule_score", sa.Float(), nullable=True)
    )
    op.add_column(
        "fraud_assessments", sa.Column("ml_probability", sa.Float(), nullable=True)
    )
    op.add_column(
        "fraud_assessments", sa.Column("combined_score", sa.Float(), nullable=True)
    )
    op.add_column(
        "fraud_assessments",
        sa.Column("model_version", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fraud_assessments", "model_version")
    op.drop_column("fraud_assessments", "combined_score")
    op.drop_column("fraud_assessments", "ml_probability")
    op.drop_column("fraud_assessments", "rule_score")
