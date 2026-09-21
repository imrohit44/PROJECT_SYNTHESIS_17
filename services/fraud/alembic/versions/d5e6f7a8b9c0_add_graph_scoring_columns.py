"""Add graph scoring columns to fraud_assessments.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9

All columns are additive and nullable: Phase 10-12 assessments keep working
with NULL graph fields. graph_signals follows the existing JSON convention
used by the reasons column.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fraud_assessments", sa.Column("graph_score", sa.Float(), nullable=True)
    )
    op.add_column(
        "fraud_assessments",
        sa.Column("graph_adjustment", sa.Float(), nullable=True),
    )
    op.add_column(
        "fraud_assessments", sa.Column("final_score", sa.Float(), nullable=True)
    )
    op.add_column(
        "fraud_assessments", sa.Column("graph_signals", sa.JSON(), nullable=True)
    )
    op.add_column(
        "fraud_assessments",
        sa.Column("graph_version", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fraud_assessments", "graph_version")
    op.drop_column("fraud_assessments", "graph_signals")
    op.drop_column("fraud_assessments", "final_score")
    op.drop_column("fraud_assessments", "graph_adjustment")
    op.drop_column("fraud_assessments", "graph_score")
