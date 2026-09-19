from fastapi import APIRouter, Depends

from backend.app.api.auth_dependencies import authorize_account, get_current_user
from backend.app.api.dependencies import get_bank, get_cache
from backend.app.api.v1.schemas import TransferRequest, TransferResponse
from backend.app.application.banking import BankApplicationService
from backend.app.infrastructure.cache import Cache
from backend.app.infrastructure.metrics import (
    record_transfer_failure,
    record_transfer_success,
)
from backend.app.security.principal import CurrentUser
from services.common.tracing import get_tracer

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post(
    "",
    response_model=TransferResponse,
    summary="Transfer money between accounts",
)
def transfer(
    request: TransferRequest,
    bank: BankApplicationService = Depends(get_bank),
    cache: Cache = Depends(get_cache),
    user: CurrentUser = Depends(get_current_user),
) -> TransferResponse:
    tracer = get_tracer(__name__)
    try:
        authorize_account(request.source_account_id, user, bank)
        with tracer.start_as_current_span("banking.transfer") as span:
            span.set_attribute("pybank.transfer.amount", f"{request.amount:.2f}")
            source, destination = bank.transfer(
                request.source_account_id,
                request.destination_account_id,
                request.amount,
            )
            span.set_attribute(
                "pybank.source_transaction_id",
                source.transactions[-1].transaction_id,
            )
    except Exception:
        record_transfer_failure()
        raise
    record_transfer_success()
    cache.delete(
        f"account:{source.account_id}",
        f"account:{destination.account_id}",
        f"customer:{source.owner.customer_id}:accounts",
        f"customer:{destination.owner.customer_id}:accounts",
    )
    return TransferResponse(
        source_account_id=source.account_id,
        destination_account_id=destination.account_id,
        amount=f"{request.amount:.2f}",
        source_transaction_id=source.transactions[-1].transaction_id,
        destination_transaction_id=destination.transactions[-1].transaction_id,
    )
