from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

from backend.app.domain.exceptions import InvalidAmountError

MONEY_PLACES = Decimal("0.01")


def normalize_amount(amount: Decimal | int | str) -> Decimal:
    """Validate and round a monetary amount to two decimal places."""

    if isinstance(amount, float):
        raise InvalidAmountError("Money must be provided as Decimal, int, or str")

    try:
        normalized = Decimal(str(amount)).quantize(
            MONEY_PLACES, rounding=ROUND_HALF_EVEN
        )
    except (InvalidOperation, ValueError) as error:
        raise InvalidAmountError("Amount must be a valid number") from error

    if not normalized.is_finite() or normalized <= 0:
        raise InvalidAmountError("Amount must be greater than zero")
    return normalized


def normalize_balance(amount: Decimal | int | str) -> Decimal:
    """Round a non-negative opening or resulting balance to cents."""

    if isinstance(amount, float):
        raise InvalidAmountError("Money must be provided as Decimal, int, or str")

    try:
        balance = Decimal(str(amount)).quantize(MONEY_PLACES, rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError) as error:
        raise InvalidAmountError("Balance must be a valid number") from error

    if not balance.is_finite() or balance < 0:
        raise InvalidAmountError("Balance cannot be negative")
    return balance
