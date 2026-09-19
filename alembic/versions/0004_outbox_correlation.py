"""Add correlation metadata to the banking outbox.

Revision ID: 0004_outbox_correlation
Revises: 0003_outbox_events

Additive nullable columns only. Existing outbox rows and existing
schema_version 1 events stay valid.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_outbox_correlation"
down_revision: str | None = "0003_outbox_events"
branch_labels: Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("traceparent", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outbox_events", "traceparent")
    op.drop_column("outbox_events", "correlation_id")
