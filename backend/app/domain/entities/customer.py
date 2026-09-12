from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

from backend.app.domain.exceptions import DomainError

if TYPE_CHECKING:
    from backend.app.domain.entities.account import Account


@dataclass(slots=True)
class Customer:
    """Identity record that composes the accounts owned by one customer."""

    name: str
    email: str
    phone: str | None = None
    customer_id: str = field(default_factory=lambda: str(uuid4()))
    _accounts: dict[str, Account] = field(default_factory=dict, init=False)

    @property
    def accounts(self) -> tuple[Account, ...]:
        return tuple(self._accounts.values())

    def add_account(self, account: Account) -> None:
        if account.owner is not self:
            raise DomainError("Account owner does not match this customer")
        if account.account_id in self._accounts:
            raise DomainError("Account is already owned by this customer")
        self._accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError as error:
            raise DomainError(f"Customer does not own account {account_id}") from error
