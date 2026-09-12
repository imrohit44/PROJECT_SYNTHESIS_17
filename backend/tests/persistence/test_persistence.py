from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from backend.app.application.banking import BankApplicationService
from backend.app.domain.exceptions import InsufficientFundsError
from backend.app.infrastructure.persistence.database import create_session_factory
from backend.app.infrastructure.persistence.models import Base, TransactionModel


@pytest.fixture
def service(tmp_path: Path) -> BankApplicationService:
    database_url = f"sqlite:///{tmp_path / 'persistence.sqlite3'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return BankApplicationService(create_session_factory(database_url))


def test_customer_account_and_transactions_persist(
    service: BankApplicationService,
) -> None:
    customer = service.register_customer("Alice", "alice@example.com")
    account = service.create_savings_account(customer.customer_id, Decimal("100.00"))
    service.deposit(account.account_id, Decimal("25.00"))
    service.withdraw(account.account_id, Decimal("10.00"))

    reloaded = service.find_account(account.account_id)

    assert reloaded.balance == Decimal("115.00")
    assert [
        item.transaction_type.value
        for item in service.list_transactions(account.account_id)
    ] == [
        "deposit",
        "withdrawal",
    ]


def test_transfer_commits_both_sides_atomically(
    service: BankApplicationService,
) -> None:
    alice = service.register_customer("Alice", "alice@example.com")
    bob = service.register_customer("Bob", "bob@example.com")
    source = service.create_current_account(
        alice.customer_id, Decimal("100.00"), overdraft_limit=Decimal("50.00")
    )
    destination = service.create_savings_account(bob.customer_id)

    service.transfer(source.account_id, destination.account_id, Decimal("125.00"))

    assert service.find_account(source.account_id).balance == Decimal("-25.00")
    assert service.find_account(destination.account_id).balance == Decimal("125.00")
    assert len(service.list_transactions(source.account_id)) == 1
    assert len(service.list_transactions(destination.account_id)) == 1


def test_failed_transfer_rolls_back_without_partial_rows(
    service: BankApplicationService,
) -> None:
    alice = service.register_customer("Alice", "alice@example.com")
    bob = service.register_customer("Bob", "bob@example.com")
    source = service.create_savings_account(alice.customer_id, Decimal("10.00"))
    destination = service.create_savings_account(bob.customer_id)

    with pytest.raises(InsufficientFundsError):
        service.transfer(source.account_id, destination.account_id, Decimal("20.00"))

    assert service.find_account(source.account_id).balance == Decimal("10.00")
    assert service.find_account(destination.account_id).balance == Decimal("0.00")
    assert service.list_transactions(source.account_id) == []
    assert service.list_transactions(destination.account_id) == []


def test_database_constraint_rejects_invalid_transaction_amount(
    service: BankApplicationService,
) -> None:
    customer = service.register_customer("Alice", "alice@example.com")
    account = service.create_savings_account(customer.customer_id)
    factory = service._session_factory

    with pytest.raises(IntegrityError):
        with factory.begin() as session:
            session.add(
                TransactionModel(
                    id="invalid",
                    account_id=account.account_id,
                    transaction_type="deposit",
                    status="completed",
                    amount=Decimal("0.00"),
                )
            )
