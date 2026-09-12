from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_bank
from backend.app.api.v1.schemas import TransferRequest, TransferResponse
from backend.app.domain.entities.bank import Bank

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post(
    "",
    response_model=TransferResponse,
    summary="Transfer money between accounts",
)
def transfer(
    request: TransferRequest, bank: Bank = Depends(get_bank)
) -> TransferResponse:
    source = bank.find_account(request.source_account_id)
    destination = bank.find_account(request.destination_account_id)
    bank.transfer(
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
