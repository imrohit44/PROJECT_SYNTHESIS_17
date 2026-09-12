from datetime import UTC
from decimal import Decimal

from backend.app.domain.entities.account import Account
from backend.app.domain.entities.current_account import CurrentAccount
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.savings_account import SavingsAccount
from backend.app.domain.entities.transaction import Transaction
from backend.app.domain.enums import AccountStatus, TransactionStatus, TransactionType
from backend.app.infrastructure.persistence.models import (
    AccountModel,
    CustomerModel,
    TransactionModel,
)


def customer_to_domain(model: CustomerModel) -> Customer:
    return Customer(model.name, model.email, model.phone, customer_id=model.id)


def account_to_domain(model: AccountModel, customer: Customer | None = None) -> Account:
    owner = customer or customer_to_domain(model.customer)
    if model.account_type == "savings":
        account: Account = SavingsAccount(
            owner,
            model.balance,
            interest_rate=model.interest_rate or Decimal("0.04"),
            minimum_balance=model.minimum_balance or Decimal("0.00"),
            account_id=model.id,
        )
    else:
        account = CurrentAccount(
            owner,
            model.balance if model.balance >= 0 else Decimal("0.00"),
            overdraft_limit=model.overdraft_limit or Decimal("0.00"),
            account_id=model.id,
        )
        account._balance = model.balance
    account._status = AccountStatus(model.status)
    account._transactions = [transaction_to_domain(item) for item in model.transactions]
    return account


def transaction_to_domain(model: TransactionModel) -> Transaction:
    timestamp = model.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return Transaction(
        transaction_type=TransactionType(model.transaction_type),
        amount=model.amount,
        source_account_id=model.source_account_id,
        destination_account_id=model.destination_account_id,
        status=TransactionStatus(model.status),
        transaction_id=model.id,
        timestamp=timestamp,
    )
