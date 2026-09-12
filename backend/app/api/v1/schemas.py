from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.enums import AccountStatus, TransactionStatus, TransactionType


class CreateCustomerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=50)


class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str | None


class AccountType(str):
    SAVINGS = "savings"
    CURRENT = "current"


class CreateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    account_type: str
    opening_balance: Decimal = Decimal("0.00")
    interest_rate: Decimal = Decimal("0.04")
    minimum_balance: Decimal = Decimal("0.00")
    overdraft_limit: Decimal = Decimal("0.00")

    @field_validator(
        "opening_balance",
        "interest_rate",
        "minimum_balance",
        "overdraft_limit",
        mode="before",
    )
    @classmethod
    def reject_float_money(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("Money values must be decimal strings, not floats")
        return value

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {AccountType.SAVINGS, AccountType.CURRENT}:
            raise ValueError("account_type must be 'savings' or 'current'")
        return normalized


class AccountResponse(BaseModel):
    account_id: str
    customer_id: str
    account_type: str
    balance: str
    status: AccountStatus
    available_balance: str | None = None
    interest_rate: str | None = None
    minimum_balance: str | None = None
    overdraft_limit: str | None = None


class MoneyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def reject_float_money(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("Money values must be decimal strings, not floats")
        return value


class TransferRequest(MoneyRequest):
    source_account_id: str
    destination_account_id: str


class TransactionResponse(BaseModel):
    transaction_id: str
    transaction_type: TransactionType
    amount: str
    timestamp: str
    status: TransactionStatus
    source_account_id: str | None
    destination_account_id: str | None


class TransferResponse(BaseModel):
    source_account_id: str
    destination_account_id: str
    amount: str
    source_transaction_id: str
    destination_transaction_id: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
