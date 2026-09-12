from decimal import Decimal

from backend.app.domain.entities.account import Account
from backend.app.domain.enums import TransactionType
from backend.app.domain.exceptions import InvalidTransferError
from backend.app.domain.money import normalize_amount


class TransferService:
    """Coordinates an all-or-nothing in-memory transfer between accounts."""

    def transfer(
        self,
        source: Account,
        destination: Account,
        amount: Decimal | int | str,
    ) -> None:
        if source is destination:
            raise InvalidTransferError("Source and destination must differ")

        normalized = normalize_amount(amount)
        source.can_withdraw(normalized)
        destination._require_active()

        source._debit_for_transfer(normalized)
        destination._credit_for_transfer(normalized)
        source._record_transaction(
            TransactionType.TRANSFER,
            normalized,
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
        )
        destination._record_transaction(
            TransactionType.TRANSFER,
            normalized,
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
        )
