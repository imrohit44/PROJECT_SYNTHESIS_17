from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from backend.app.security.roles import UserRole


class TokenError(Exception):
    """Raised when a JWT cannot be trusted or has the wrong purpose."""


# Hardening: the service only ever issues HS256 tokens, so it must only ever
# accept HS256 tokens. Allowing the caller to choose any algorithm invites
# algorithm-confusion attacks (a public key presented as an HMAC secret).
_ALLOWED_ALGORITHMS = ("HS256",)


class TokenService:
    def __init__(
        self, secret: str, algorithm: str, access_minutes: int, refresh_days: int
    ) -> None:
        if not secret or len(secret) < 32:
            raise TokenError("JWT secret must be at least 32 characters")
        if algorithm.upper() != _ALLOWED_ALGORITHMS[0]:
            raise TokenError(f"Unsupported JWT algorithm: {algorithm}")
        self._secret = secret
        self._algorithm = _ALLOWED_ALGORITHMS[0]
        self._access_minutes = access_minutes
        self._refresh_days = refresh_days

    def create_access_token(self, user_id: str, role: UserRole) -> str:
        return self._encode(
            user_id, role, "access", timedelta(minutes=self._access_minutes)
        )

    def create_refresh_token(self, user_id: str, role: UserRole) -> str:
        return self._encode(
            user_id, role, "refresh", timedelta(days=self._refresh_days)
        )

    def decode(self, token: str, expected_type: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError as error:
            raise TokenError("Invalid token") from error
        required = ("sub", "role", "type", "iat", "exp")
        if any(claim not in payload for claim in required):
            raise TokenError("Invalid token")
        if payload.get("type") != expected_type or not payload.get("sub"):
            raise TokenError("Invalid token")
        try:
            UserRole(str(payload["role"]))
        except ValueError as error:
            raise TokenError("Invalid token") from error
        if payload.get("type") not in {"access", "refresh"}:
            raise TokenError("Invalid token")
        return payload

    def _encode(
        self, user_id: str, role: UserRole, token_type: str, lifetime: timedelta
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "role": role.value,
            "type": token_type,
            "iat": now,
            "exp": now + lifetime,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)
