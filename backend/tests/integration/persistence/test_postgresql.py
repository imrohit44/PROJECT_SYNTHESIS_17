from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.banking import BankApplicationService
from backend.app.infrastructure.persistence.models import AccountModel, CustomerModel

pytestmark = pytest.mark.integration


def test_postgresql_numeric_constraints_and_foreign_keys(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    service = BankApplicationService(postgres_session_factory)
    customer = service.register_customer("Postgres User", "postgres-user@example.test")
    account = service.create_savings_account(customer.customer_id, Decimal("10.129"))

    assert service.find_account(account.account_id).balance == Decimal("10.13")

    with pytest.raises(IntegrityError):
        with postgres_session_factory.begin() as session:
            session.add(
                AccountModel(
                    id="bad-account",
                    customer_id="missing-customer",
                    account_type="savings",
                    balance=Decimal("1.00"),
                    status="active",
                )
            )


def test_postgresql_transaction_rollback_keeps_state_isolated(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(RuntimeError, match="force rollback"):
        with postgres_session_factory.begin() as session:
            session.add(
                CustomerModel(
                    id="rollback-customer",
                    name="Rollback",
                    email="rollback@example.test",
                )
            )
            raise RuntimeError("force rollback")

    with postgres_session_factory() as session:
        assert (
            session.scalar(
                select(CustomerModel).where(CustomerModel.id == "rollback-customer")
            )
            is None
        )


def test_postgresql_row_locking_clause_is_supported(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    service = BankApplicationService(postgres_session_factory)
    customer = service.register_customer("Lock User", "lock-user@example.test")
    account = service.create_current_account(customer.customer_id, Decimal("20.00"))

    with postgres_session_factory.begin() as session:
        locked = session.execute(
            text("SELECT id FROM accounts WHERE id = :id FOR UPDATE"),
            {"id": account.account_id},
        ).scalar_one()

    assert locked == account.account_id
