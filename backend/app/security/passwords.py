from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError


class PasswordService:
    """Application-facing password hashing boundary."""

    def __init__(self) -> None:
        self._hasher = Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, VerifyMismatchError):
            return False
