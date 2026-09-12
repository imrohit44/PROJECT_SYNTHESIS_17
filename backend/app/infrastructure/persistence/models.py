from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CustomerModel(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    accounts: Mapped[list["AccountModel"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class AccountModel(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "balance >= 0 OR account_type = 'current'", name="ck_account_balance"
        ),
        CheckConstraint(
            "account_type IN ('savings', 'current')", name="ck_account_type"
        ),
        CheckConstraint(
            "status IN ('active', 'frozen', 'closed')", name="ck_account_status"
        ),
        Index("ix_accounts_customer_id", "customer_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    minimum_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    overdraft_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    customer: Mapped[CustomerModel] = relationship(back_populates="accounts")
    transactions: Mapped[list["TransactionModel"]] = relationship(
        back_populates="account", foreign_keys="TransactionModel.account_id"
    )


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transaction_amount"),
        Index("ix_transactions_account_id", "account_id"),
        Index("ix_transactions_source_account_id", "source_account_id"),
        Index("ix_transactions_destination_account_id", "destination_account_id"),
        Index("ix_transactions_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    source_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    destination_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id")
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    account: Mapped[AccountModel] = relationship(
        back_populates="transactions", foreign_keys=[account_id]
    )
