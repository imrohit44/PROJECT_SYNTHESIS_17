from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from backend.app.application.events import (
    account_created_event,
    deposit_completed_event,
    transfer_completed_event,
    withdrawal_completed_event,
)
from backend.app.domain.entities.account import Account
from backend.app.domain.entities.current_account import CurrentAccount
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.savings_account import SavingsAccount
from backend.app.domain.enums import TransactionStatus
from backend.app.domain.services.transfer import TransferService
from backend.app.infrastructure.outbox import add_outbox_event
from backend.app.infrastructure.persistence.mappers import (
    account_to_domain,
    customer_to_domain,
    transaction_to_domain,
)
from backend.app.infrastructure.persistence.models import (
    AccountModel,
    CustomerModel,
    TransactionModel,
)


class BankApplicationService:
    """Application boundary coordinating domain rules and persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._transfer_service = TransferService()

    def register_customer(
        self, name: str, email: str, phone: str | None = None
    ) -> Customer:
        customer = Customer(name=name, email=email, phone=phone)
        with self._session_factory.begin() as session:
            session.add(
                CustomerModel(
                    id=customer.customer_id,
                    name=customer.name,
                    email=customer.email,
                    phone=customer.phone,
                )
            )
        return customer

    def find_customer(self, customer_id: str) -> Customer:
        with self._session_factory() as session:
            model = session.get(CustomerModel, customer_id)
            if model is None:
                from backend.app.domain.exceptions import CustomerNotFoundError

                raise CustomerNotFoundError(customer_id)
            return customer_to_domain(model)

    def create_savings_account(
        self,
        customer_id: str,
        opening_balance: Decimal | int | str = Decimal("0.00"),
        **kwargs: Any,
    ) -> SavingsAccount:
        customer, account = self._create_account(
            customer_id, "savings", opening_balance, **kwargs
        )
        assert isinstance(account, SavingsAccount)
        return account

    def create_current_account(
        self,
        customer_id: str,
        opening_balance: Decimal | int | str = Decimal("0.00"),
        **kwargs: Any,
    ) -> CurrentAccount:
        _, account = self._create_account(
            customer_id, "current", opening_balance, **kwargs
        )
        assert isinstance(account, CurrentAccount)
        return account

    def _create_account(
        self,
        customer_id: str,
        account_type: str,
        opening_balance: Decimal | int | str,
        **kwargs: Any,
    ) -> tuple[Customer, Account]:
        with self._session_factory.begin() as session:
            customer_model = session.get(CustomerModel, customer_id)
            if customer_model is None:
                from backend.app.domain.exceptions import CustomerNotFoundError

                raise CustomerNotFoundError(customer_id)
            customer = customer_to_domain(customer_model)
            account: Account
            if account_type == "savings":
                account = SavingsAccount(customer, opening_balance, **kwargs)
            else:
                account = CurrentAccount(customer, opening_balance, **kwargs)
            model = AccountModel(
                id=account.account_id,
                customer_id=customer_id,
                account_type=account_type,
                balance=account.balance,
                status=account.status.value,
                interest_rate=getattr(account, "interest_rate", None),
                minimum_balance=getattr(account, "minimum_balance", None),
                overdraft_limit=getattr(account, "overdraft_limit", None),
            )
            session.add(model)
            add_outbox_event(
                session,
                account_created_event(account.account_id, customer_id, account_type),
            )
        return customer, account

    def find_account(self, account_id: str) -> Account:
        with self._session_factory() as session:
            model = session.execute(
                self._account_query().where(AccountModel.id == account_id)
            ).scalar_one_or_none()
            if model is None:
                from backend.app.domain.exceptions import AccountNotFoundError

                raise AccountNotFoundError(account_id)
            return account_to_domain(model)

    def list_accounts(self, customer_id: str) -> list[Account]:
        with self._session_factory() as session:
            models = session.scalars(
                self._account_query()
                .where(AccountModel.customer_id == customer_id)
                .order_by(AccountModel.created_at)
            ).all()
            return [account_to_domain(model) for model in models]

    def account_owner_id(self, account_id: str) -> str:
        with self._session_factory() as session:
            owner_id = session.scalar(
                select(AccountModel.customer_id).where(AccountModel.id == account_id)
            )
            if owner_id is None:
                from backend.app.domain.exceptions import AccountNotFoundError

                raise AccountNotFoundError(account_id)
            return owner_id

    def deposit(self, account_id: str, amount: Decimal | int | str) -> Account:
        with self._session_factory.begin() as session:
            model = self._locked_account(session, account_id)
            account = account_to_domain(model)
            transaction = account.deposit(amount)
            model.balance = account.balance
            session.add(self._transaction_model(account_id, transaction))
            add_outbox_event(
                session,
                deposit_completed_event(
                    account_id,
                    account.owner.customer_id,
                    transaction.amount,
                    transaction.transaction_id,
                ),
            )
            return account

    def withdraw(self, account_id: str, amount: Decimal | int | str) -> Account:
        with self._session_factory.begin() as session:
            model = self._locked_account(session, account_id)
            account = account_to_domain(model)
            transaction = account.withdraw(amount)
            model.balance = account.balance
            session.add(self._transaction_model(account_id, transaction))
            add_outbox_event(
                session,
                withdrawal_completed_event(
                    account_id,
                    account.owner.customer_id,
                    transaction.amount,
                    transaction.transaction_id,
                ),
            )
            return account

    def list_transactions(self, account_id: str) -> list:
        with self._session_factory() as session:
            model = session.execute(
                self._account_query().where(AccountModel.id == account_id)
            ).scalar_one_or_none()
            if model is None:
                from backend.app.domain.exceptions import AccountNotFoundError

                raise AccountNotFoundError(account_id)
            return [transaction_to_domain(item) for item in model.transactions]

    def freeze_account(self, account_id: str) -> None:
        self._change_account_status(account_id, "freeze")

    def activate_account(self, account_id: str) -> None:
        self._change_account_status(account_id, "activate")

    def close_account(self, account_id: str) -> None:
        self._change_account_status(account_id, "close")

    def _change_account_status(self, account_id: str, operation: str) -> None:
        with self._session_factory.begin() as session:
            model = self._locked_account(session, account_id)
            account = account_to_domain(model)
            getattr(account, operation)()
            model.status = account.status.value

    def transfer(
        self,
        source_account_id: str,
        destination_account_id: str,
        amount: Decimal | int | str,
    ) -> tuple[Account, Account]:
        if source_account_id == destination_account_id:
            from backend.app.domain.exceptions import InvalidTransferError

            raise InvalidTransferError("Source and destination must differ")
        with self._session_factory.begin() as session:
            account_ids = sorted((source_account_id, destination_account_id))
            locked_models = {
                account_id: self._locked_account(session, account_id)
                for account_id in account_ids
            }
            source_model = locked_models[source_account_id]
            destination_model = locked_models[destination_account_id]
            source = account_to_domain(source_model)
            destination = account_to_domain(destination_model)
            normalized = source.can_withdraw(amount)
            destination._require_active()
            self._transfer_service.transfer(source, destination, normalized)
            source_model.balance = source.balance
            destination_model.balance = destination.balance
            session.add(
                self._transaction_model(source.account_id, source.transactions[-1])
            )
            session.add(
                self._transaction_model(
                    destination.account_id, destination.transactions[-1]
                )
            )
            add_outbox_event(
                session,
                transfer_completed_event(
                    source.account_id,
                    destination.account_id,
                    source.owner.customer_id,
                    destination.owner.customer_id,
                    source.transactions[-1].amount,
                    source.transactions[-1].transaction_id,
                    destination.transactions[-1].transaction_id,
                ),
            )
            return source, destination

    def _locked_account(self, session: Session, account_id: str) -> AccountModel:
        model = session.execute(
            self._account_query()
            .with_for_update(of=AccountModel)
            .where(AccountModel.id == account_id)
        ).scalar_one_or_none()

        if model is None:
            from backend.app.domain.exceptions import AccountNotFoundError

            raise AccountNotFoundError(account_id)
        return model

    @staticmethod
    def _account_query() -> Any:
        return select(AccountModel).options(
            joinedload(AccountModel.customer),
            selectinload(AccountModel.transactions),
        )

    @staticmethod
    def _transaction_model(account_id: str, transaction: Any) -> TransactionModel:
        return TransactionModel(
            id=transaction.transaction_id,
            account_id=account_id,
            transaction_type=transaction.transaction_type.value,
            status=TransactionStatus.COMPLETED.value,
            amount=transaction.amount,
            source_account_id=transaction.source_account_id,
            destination_account_id=transaction.destination_account_id,
            timestamp=transaction.timestamp,
        )
