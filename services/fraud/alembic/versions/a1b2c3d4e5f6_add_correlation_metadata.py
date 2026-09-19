"""Add correlation metadata to fraud tables.

Revision ID: a1b2c3d4e5f6
Revises: 80b35ba7f66f

correlation_id and traceparent are additive nullable columns. Existing rows and
existing schema_version 1 events remain valid; consumers that ignore the new
columns keep working.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "80b35ba7f66f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fraud_assessments",
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("traceparent", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_fraud_outbox_published_at", "outbox_events", ["published_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_fraud_outbox_published_at", table_name="outbox_events")
    op.drop_column("outbox_events", "traceparent")
    op.drop_column("outbox_events", "correlation_id")
    op.drop_column("fraud_assessments", "correlation_id")