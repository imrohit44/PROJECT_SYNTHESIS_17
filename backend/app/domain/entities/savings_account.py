from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from backend.app.domain.entities.account import Account
from backend.app.domain.enums import TransactionType
from backend.app.domain.exceptions import InsufficientFundsError
from backend.app.domain.money import normalize_balance

if TYPE_CHECKING:
    from backend.app.domain.entities.customer import Customer


class SavingsAccount(Account):
    """Account that requires a minimum balance after withdrawals."""

    def __init__(
        self,
        owner: Customer,
        opening_balance: Decimal | int | str = Decimal("0.00"),
        interest_rate: Decimal | int | str = Decimal("0.04"),
        minimum_balance: Decimal | int | str = Decimal("0.00"),
        account_id: str | None = None,
    ) -> None:
        super().__init__(owner, opening_balance, account_id)
        self.interest_rate = Decimal(str(interest_rate))
        self.minimum_balance = normalize_balance(minimum_balance)
        if self.interest_rate < 0 or self.minimum_balance < 0:
            raise ValueError("Savings rate and minimum balance cannot be negative")
        if self.balance < self.minimum_balance:
            raise ValueError("Opening balance must meet the minimum balance")

    def _validate_withdrawal(self, amount: Decimal) -> None:
        if self.balance - amount < self.minimum_balance:
            raise InsufficientFundsError("Withdrawal would breach minimum balance")

    def calculate_interest(self) -> Decimal:
        return (self.balance * self.interest_rate).quantize(Decimal("0.01"))

    def apply_interest(self) -> None:
        interest = self.calculate_interest()
        if interest > 0:
            self.deposit(interest, TransactionType.INTEREST)
