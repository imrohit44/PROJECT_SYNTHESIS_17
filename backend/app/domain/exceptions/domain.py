class DomainError(Exception):
    """Base exception for all banking domain failures."""


class CustomerError(DomainError):
    """Base exception for customer-related failures."""


class CustomerNotFoundError(CustomerError):
    """Raised when a requested customer does not exist."""


class AccountError(DomainError):
    """Base exception for account-related failures."""


class AccountNotFoundError(AccountError):
    """Raised when a requested account does not exist."""


class AccountNotActiveError(AccountError):
    """Raised when an account cannot perform an operation in its state."""


class AccountStateError(AccountError):
    """Raised when an invalid account state transition is requested."""


class InsufficientFundsError(AccountError):
    """Raised when an account cannot cover a withdrawal."""


class InvalidAmountError(DomainError):
    """Raised when a monetary amount is not positive and valid."""


class InvalidTransferError(DomainError):
    """Raised when a transfer violates a transfer invariant."""
