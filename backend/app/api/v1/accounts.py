from fastapi import APIRouter, Depends, status

from backend.app.api.dependencies import get_bank
from backend.app.api.v1.schemas import (
    AccountResponse,
    CreateAccountRequest,
    MoneyRequest,
    TransactionResponse,
)
from backend.app.api.v1.serializers import account_response, transaction_response
from backend.app.domain.entities.account import Account
from backend.app.domain.entities.bank import Bank

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
def create_account(
    request: CreateAccountRequest, bank: Bank = Depends(get_bank)
) -> AccountResponse:
    account: Account
    if request.account_type == "savings":
        account = bank.create_savings_account(
            request.customer_id,
            request.opening_balance,
            interest_rate=request.interest_rate,
            minimum_balance=request.minimum_balance,
        )
    else:
        account = bank.create_current_account(
            request.customer_id,
            request.opening_balance,
            overdraft_limit=request.overdraft_limit,
        )
    return account_response(account)


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Retrieve an account",
)
def get_account(account_id: str, bank: Bank = Depends(get_bank)) -> AccountResponse:
    return account_response(bank.find_account(account_id))


@router.post(
    "/{account_id}/deposit",
    response_model=AccountResponse,
    summary="Deposit money into an account",
)
def deposit(
    account_id: str,
    request: MoneyRequest,
    bank: Bank = Depends(get_bank),
) -> AccountResponse:
    account = bank.find_account(account_id)
    account.deposit(request.amount)
    return account_response(account)


@router.post(
    "/{account_id}/withdraw",
    response_model=AccountResponse,
    summary="Withdraw money from an account",
)
def withdraw(
    account_id: str,
    request: MoneyRequest,
    bank: Bank = Depends(get_bank),
) -> AccountResponse:
    account = bank.find_account(account_id)
    account.withdraw(request.amount)
    return account_response(account)


@router.get(
    "/{account_id}/transactions",
    response_model=list[TransactionResponse],
    summary="Retrieve account transaction history",
)
def list_transactions(
    account_id: str, bank: Bank = Depends(get_bank)
) -> list[TransactionResponse]:
    account = bank.find_account(account_id)
    return [transaction_response(item) for item in account.transactions]
