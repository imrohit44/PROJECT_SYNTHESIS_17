from decimal import Decimal

from backend.app.api.v1.schemas import (
    AccountResponse,
    CustomerResponse,
    TransactionResponse,
)
from backend.app.domain.entities.account import Account
from backend.app.domain.entities.current_account import CurrentAccount
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.savings_account import SavingsAccount
from backend.app.domain.entities.transaction import Transaction


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def customer_response(customer: Customer) -> CustomerResponse:
    return CustomerResponse(
        customer_id=customer.customer_id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
    )


def account_response(account: Account) -> AccountResponse:
    account_type = "savings" if isinstance(account, SavingsAccount) else "current"
    return AccountResponse(
        account_id=account.account_id,
        customer_id=account.owner.customer_id,
        account_type=account_type,
        balance=money(account.balance),
        status=account.status,
        available_balance=(
            money(account.available_balance)
            if isinstance(account, CurrentAccount)
            else None
        ),
        interest_rate=(
            money(account.interest_rate)
            if isinstance(account, SavingsAccount)
            else None
        ),
        minimum_balance=(
            money(account.minimum_balance)
            if isinstance(account, SavingsAccount)
            else None
        ),
        overdraft_limit=(
            money(account.overdraft_limit)
            if isinstance(account, CurrentAccount)
            else None
        ),
    )


def transaction_response(transaction: Transaction) -> TransactionResponse:
    return TransactionResponse(
        transaction_id=transaction.transaction_id,
        transaction_type=transaction.transaction_type,
        amount=money(transaction.amount),
        timestamp=transaction.timestamp.isoformat(),
        status=transaction.status,
        source_account_id=transaction.source_account_id,
        destination_account_id=transaction.destination_account_id,
    )
