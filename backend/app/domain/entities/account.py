from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from backend.app.domain.entities.transaction import Transaction
from backend.app.domain.enums import AccountStatus, TransactionType
from backend.app.domain.exceptions import (
    AccountNotActiveError,
    AccountStateError,
)
from backend.app.domain.money import normalize_amount, normalize_balance

if TYPE_CHECKING:
    from backend.app.domain.entities.customer import Customer


class Account(ABC):
    """Base account abstraction that owns balance and transaction invariants."""

    def __init__(
        self,
        owner: Customer,
        opening_balance: Decimal | int | str = Decimal("0.00"),
        account_id: str | None = None,
    ) -> None:
        self.account_id = account_id or str(uuid4())
        self.owner = owner
        self._balance = normalize_balance(opening_balance)
        self._status = AccountStatus.ACTIVE
        self._transactions: list[Transaction] = []

    @property
    def balance(self) -> Decimal:
        return self._balance

    @property
    def status(self) -> AccountStatus:
        return self._status

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._transactions)

    def freeze(self) -> None:
        if self._status is AccountStatus.CLOSED:
            raise AccountStateError("A closed account cannot be frozen")
        self._status = AccountStatus.FROZEN

    def activate(self) -> None:
        if self._status is AccountStatus.CLOSED:
            raise AccountStateError("A closed account cannot be activated")
        self._status = AccountStatus.ACTIVE

    def close(self) -> None:
        if self._status is AccountStatus.CLOSED:
            raise AccountStateError("Account is already closed")
        self._status = AccountStatus.CLOSED

    def deposit(
        self,
        amount: Decimal | int | str,
        transaction_type: TransactionType = TransactionType.DEPOSIT,
    ) -> Transaction:
        self._require_active()
        normalized = normalize_amount(amount)
        self._balance += normalized
        return self._record_transaction(transaction_type, normalized)

    def withdraw(self, amount: Decimal | int | str) -> Transaction:
        self._require_active()
        normalized = normalize_amount(amount)
        self._validate_withdrawal(normalized)
        self._balance -= normalized
        return self._record_transaction(TransactionType.WITHDRAWAL, normalized)

    def can_withdraw(self, amount: Decimal | int | str) -> Decimal:
        self._require_active()
        normalized = normalize_amount(amount)
        self._validate_withdrawal(normalized)
        return normalized

    def _debit_for_transfer(self, amount: Decimal) -> None:
        self._balance -= amount

    def _credit_for_transfer(self, amount: Decimal) -> None:
        self._balance += amount

    def _record_transaction(
        self,
        transaction_type: TransactionType,
        amount: Decimal,
        *,
        source_account_id: str | None = None,
        destination_account_id: str | None = None,
    ) -> Transaction:
        transaction = Transaction(
            transaction_type=transaction_type,
            amount=amount,
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
        )
        self._transactions.append(transaction)
        return transaction

    def _require_active(self) -> None:
        if self._status is not AccountStatus.ACTIVE:
            raise AccountNotActiveError(
                f"Account {self.account_id} is {self._status.value}"
            )

    @abstractmethod
    def _validate_withdrawal(self, amount: Decimal) -> None:
        """Enforce account-specific withdrawal rules before mutation."""


__all__ = ["Account"]
