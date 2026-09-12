from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from backend.app.domain.entities.account import Account
from backend.app.domain.exceptions import InsufficientFundsError
from backend.app.domain.money import normalize_balance

if TYPE_CHECKING:
    from backend.app.domain.entities.customer import Customer


class CurrentAccount(Account):
    """Account that permits withdrawals up to balance plus overdraft limit."""

    def __init__(
        self,
        owner: Customer,
        opening_balance: Decimal | int | str = Decimal("0.00"),
        overdraft_limit: Decimal | int | str = Decimal("0.00"),
        account_id: str | None = None,
    ) -> None:
        super().__init__(owner, opening_balance, account_id)
        self.overdraft_limit = normalize_balance(overdraft_limit)

    @property
    def available_balance(self) -> Decimal:
        return self.balance + self.overdraft_limit

    def _validate_withdrawal(self, amount: Decimal) -> None:
        if amount > self.available_balance:
            raise InsufficientFundsError("Withdrawal exceeds the overdraft limit")
