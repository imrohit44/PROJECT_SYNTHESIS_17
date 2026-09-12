from decimal import Decimal

import pytest

from backend.app.domain.entities.bank import Bank
from backend.app.domain.entities.current_account import CurrentAccount
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.savings_account import SavingsAccount
from backend.app.domain.entities.transaction import Transaction
from backend.app.domain.enums import AccountStatus, TransactionType
from backend.app.domain.exceptions import (
    AccountNotActiveError,
    AccountStateError,
    InsufficientFundsError,
    InvalidAmountError,
    InvalidTransferError,
)


def test_customer_and_account_composition() -> None:
    customer = Customer("Alice", "alice@example.com")
    account = SavingsAccount(customer)
    customer.add_account(account)

    assert account.owner is customer
    assert customer.accounts == (account,)


def test_deposit_withdrawal_and_transaction_recording() -> None:
    customer = Customer("Alice", "alice@example.com")
    account = SavingsAccount(customer, opening_balance=Decimal("100.00"))

    deposit = account.deposit(Decimal("25.125"))
    withdrawal = account.withdraw(Decimal("10.00"))

    assert account.balance == Decimal("115.12")
    assert deposit.transaction_type is TransactionType.DEPOSIT
    assert withdrawal.transaction_type is TransactionType.WITHDRAWAL
    assert len(account.transactions) == 2


def test_invalid_amounts_are_rejected() -> None:
    account = SavingsAccount(Customer("Alice", "alice@example.com"))

    with pytest.raises(InvalidAmountError):
        account.deposit(Decimal("0"))
    with pytest.raises(InvalidAmountError):
        account.withdraw(Decimal("-1"))
    with pytest.raises(InvalidAmountError):
        account.deposit(0.1)  # type: ignore[arg-type]
    with pytest.raises(InvalidAmountError):
        SavingsAccount(Customer("Bob", "bob@example.com"), opening_balance=0.1)  # type: ignore[arg-type]


def test_savings_minimum_balance_and_interest() -> None:
    account = SavingsAccount(
        Customer("Alice", "alice@example.com"),
        opening_balance=Decimal("100.00"),
        minimum_balance=Decimal("50.00"),
        interest_rate=Decimal("0.05"),
    )

    with pytest.raises(InsufficientFundsError):
        account.withdraw(Decimal("51.00"))

    account.apply_interest()

    assert account.balance == Decimal("105.00")
    assert account.transactions[-1].transaction_type is TransactionType.INTEREST


def test_current_account_exposes_overdraft_as_available_balance() -> None:
    account = CurrentAccount(
        Customer("Bob", "bob@example.com"),
        opening_balance=Decimal("1000.00"),
        overdraft_limit=Decimal("2000.00"),
    )

    account.withdraw(Decimal("2000.00"))

    assert account.balance == Decimal("-1000.00")
    assert account.available_balance == Decimal("1000.00")
    with pytest.raises(InsufficientFundsError):
        account.withdraw(Decimal("1000.01"))


def test_account_states_control_operations_and_transitions() -> None:
    account = SavingsAccount(Customer("Alice", "alice@example.com"))
    account.freeze()

    assert account.status is AccountStatus.FROZEN
    with pytest.raises(AccountNotActiveError):
        account.deposit(Decimal("10.00"))

    account.activate()
    account.close()
    with pytest.raises(AccountStateError):
        account.activate()


def test_bank_transfer_updates_both_accounts_and_records_transactions() -> None:
    bank = Bank("PyBank")
    alice = bank.register_customer("Alice", "alice@example.com")
    bob = bank.register_customer("Bob", "bob@example.com")
    source = bank.create_current_account(alice.customer_id, Decimal("100.00"))
    destination = bank.create_savings_account(bob.customer_id)

    bank.transfer(source.account_id, destination.account_id, Decimal("40.00"))

    assert source.balance == Decimal("60.00")
    assert destination.balance == Decimal("40.00")
    assert source.transactions[-1].source_account_id == source.account_id
    assert destination.transactions[-1].destination_account_id == destination.account_id


def test_failed_transfer_is_atomic_and_same_account_is_invalid() -> None:
    bank = Bank("PyBank")
    customer = bank.register_customer("Alice", "alice@example.com")
    source = bank.create_savings_account(customer.customer_id, Decimal("10.00"))
    destination = bank.create_savings_account(customer.customer_id)
    initial_source_transactions = source.transactions
    initial_destination_transactions = destination.transactions

    with pytest.raises(InsufficientFundsError):
        bank.transfer(source.account_id, destination.account_id, Decimal("20.00"))

    assert source.balance == Decimal("10.00")
    assert destination.balance == Decimal("0.00")
    assert source.transactions == initial_source_transactions
    assert destination.transactions == initial_destination_transactions

    with pytest.raises(InvalidTransferError):
        bank.transfer(source.account_id, source.account_id, Decimal("1.00"))


def test_transaction_is_immutable() -> None:
    transaction = Transaction(TransactionType.DEPOSIT, Decimal("10.00"))

    with pytest.raises(AttributeError):
        transaction.amount = Decimal("20.00")  # type: ignore[misc]
