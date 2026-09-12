from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.app.domain.entities.account import Account
from backend.app.domain.entities.current_account import CurrentAccount
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.savings_account import SavingsAccount
from backend.app.domain.exceptions import AccountNotFoundError, CustomerNotFoundError
from backend.app.domain.services.transfer import TransferService


class Bank:
    """Registry and coordination boundary for customers and their accounts."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._customers: dict[str, Customer] = {}
        self._accounts: dict[str, Account] = {}
        self._transfer_service = TransferService()

    @property
    def customers(self) -> tuple[Customer, ...]:
        return tuple(self._customers.values())

    def register_customer(
        self, name: str, email: str, phone: str | None = None
    ) -> Customer:
        customer = Customer(name=name, email=email, phone=phone)
        self._customers[customer.customer_id] = customer
        return customer

    def find_customer(self, customer_id: str) -> Customer:
        try:
            return self._customers[customer_id]
        except KeyError as error:
            raise CustomerNotFoundError(customer_id) from error

    def create_savings_account(
        self,
        customer_id: str,
        opening_balance: Decimal | int | str = Decimal("0.00"),
        **kwargs: Any,
    ) -> SavingsAccount:
        customer = self.find_customer(customer_id)
        account = SavingsAccount(customer, opening_balance, **kwargs)
        self._register_account(customer, account)
        return account

    def create_current_account(
        self,
        customer_id: str,
        opening_balance: Decimal | int | str = Decimal("0.00"),
        **kwargs: Any,
    ) -> CurrentAccount:
        customer = self.find_customer(customer_id)
        account = CurrentAccount(customer, opening_balance, **kwargs)
        self._register_account(customer, account)
        return account

    def find_account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError as error:
            raise AccountNotFoundError(account_id) from error

    def transfer(
        self,
        source_account_id: str,
        destination_account_id: str,
        amount: Decimal | int | str,
    ) -> None:
        source = self.find_account(source_account_id)
        destination = self.find_account(destination_account_id)
        self._transfer_service.transfer(source, destination, amount)

    def _register_account(self, customer: Customer, account: Account) -> None:
        customer.add_account(account)
        self._accounts[account.account_id] = account
