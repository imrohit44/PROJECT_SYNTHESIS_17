"""Create the Phase 3 banking schema.

Revision ID: 0001_initial_schema
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(50)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_customers_email"),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False
        ),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("interest_rate", sa.Numeric(9, 6)),
        sa.Column("minimum_balance", sa.Numeric(18, 2)),
        sa.Column("overdraft_limit", sa.Numeric(18, 2)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "balance >= 0 OR account_type = 'current'", name="ck_account_balance"
        ),
        sa.CheckConstraint(
            "account_type IN ('savings', 'current')", name="ck_account_type"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'frozen', 'closed')", name="ck_account_status"
        ),
    )
    op.create_index("ix_accounts_customer_id", "accounts", ["customer_id"])
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("source_account_id", sa.String(36), sa.ForeignKey("accounts.id")),
        sa.Column(
            "destination_account_id", sa.String(36), sa.ForeignKey("accounts.id")
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_transaction_amount"),
    )
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index(
        "ix_transactions_source_account_id", "transactions", ["source_account_id"]
    )
    op.create_index(
        "ix_transactions_destination_account_id",
        "transactions",
        ["destination_account_id"],
    )
    op.create_index("ix_transactions_timestamp", "transactions", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_transactions_timestamp", table_name="transactions")
    op.drop_index("ix_transactions_destination_account_id", table_name="transactions")
    op.drop_index("ix_transactions_source_account_id", table_name="transactions")
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_accounts_customer_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("customers")
