from fastapi import APIRouter, Depends, status

from backend.app.api.auth_dependencies import (
    authorize_account,
    authorize_customer,
    get_current_user,
)
from backend.app.api.dependencies import get_bank
from backend.app.api.v1.schemas import (
    AccountResponse,
    CreateAccountRequest,
    MoneyRequest,
    TransactionResponse,
)
from backend.app.api.v1.serializers import account_response, transaction_response
from backend.app.application.banking import BankApplicationService
from backend.app.domain.entities.account import Account
from backend.app.security.principal import CurrentUser

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse], summary="List owned accounts")
def list_accounts(
    bank: BankApplicationService = Depends(get_bank),
    user: CurrentUser = Depends(get_current_user),
) -> list[AccountResponse]:
    return [
        account_response(account) for account in bank.list_accounts(user.customer_id)
    ]


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
def create_account(
    request: CreateAccountRequest,
    bank: BankApplicationService = Depends(get_bank),
    user: CurrentUser = Depends(get_current_user),
) -> AccountResponse:
    authorize_customer(user, request.customer_id)
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
def get_account(
    account_id: str,
    bank: BankApplicationService = Depends(get_bank),
    user: CurrentUser = Depends(get_current_user),
) -> AccountResponse:
    authorize_account(account_id, user, bank)
    return account_response(bank.find_account(account_id))


@router.post(
    "/{account_id}/deposit",
    response_model=AccountResponse,
    summary="Deposit money into an account",
)
def deposit(
    account_id: str,
    request: MoneyRequest,
    bank: BankApplicationService = Depends(get_bank),
    user: CurrentUser = Depends(get_current_user),
) -> AccountResponse:
    authorize_account(account_id, user, bank)
    return account_response(bank.deposit(account_id, request.amount))


@router.post(
    "/{account_id}/withdraw",
    response_model=AccountResponse,
    summary="Withdraw money from an account",
)
def withdraw(
    account_id: str,
    request: MoneyRequest,
    bank: BankApplicationService = Depends(get_bank),
    user: CurrentUser = Depends(get_current_user),
) -> AccountResponse:
    authorize_account(account_id, user, bank)
    return account_response(bank.withdraw(account_id, request.amount))


@router.get(
    "/{account_id}/transactions",
    response_model=list[TransactionResponse],
    summary="Retrieve account transaction history",
)
def list_transactions(
    account_id: str,
    bank: BankApplicationService = Depends(get_bank),
    user: CurrentUser = Depends(get_current_user),
) -> list[TransactionResponse]:
    authorize_account(account_id, user, bank)
    account = bank.find_account(account_id)
    return [transaction_response(item) for item in account.transactions]
