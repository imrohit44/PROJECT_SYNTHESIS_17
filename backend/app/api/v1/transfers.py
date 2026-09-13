from fastapi import APIRouter, Depends

from backend.app.api.auth_dependencies import authorize_account, get_current_user
from backend.app.api.dependencies import get_bank
from backend.app.api.v1.schemas import TransferRequest, TransferResponse
from backend.app.application.banking import BankApplicationService
from backend.app.security.principal import CurrentUser

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post(
    "",
    response_model=TransferResponse,
    summary="Transfer money between accounts",
)
def transfer(
    request: TransferRequest,
    bank: BankApplicationService = Depends(get_bank),
    user: CurrentUser = Depends(get_current_user),
) -> TransferResponse:
    authorize_account(request.source_account_id, user, bank)
    source, destination = bank.transfer(
        request.source_account_id,
        request.destination_account_id,
        request.amount,
    )
    return TransferResponse(
        source_account_id=source.account_id,
        destination_account_id=destination.account_id,
        amount=f"{request.amount:.2f}",
        source_transaction_id=source.transactions[-1].transaction_id,
        destination_transaction_id=destination.transactions[-1].transaction_id,
    )
