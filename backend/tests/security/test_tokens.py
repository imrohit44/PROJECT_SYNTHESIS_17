"""Phase 17 token-hardening regression tests.

The service must only ever trust HS256 tokens it could plausibly have signed
itself: short/empty secrets, non-HS256 configurations, forged ``alg=none``
tokens, foreign signatures, and expired tokens must all be refused.
"""

from __future__ import annotations

import jwt as pyjwt
import pytest

from backend.app.security.roles import UserRole
from backend.app.security.tokens import TokenError, TokenService

SECRET = "test-secret-that-is-at-least-32-bytes-long"

pytestmark = pytest.mark.security


def _service(secret: str = SECRET, algorithm: str = "HS256") -> TokenService:
    return TokenService(secret, algorithm, 15, 7)


def test_short_secret_is_refused_at_construction():
    with pytest.raises(TokenError):
        _service(secret="too-short")


def test_empty_secret_is_refused_at_construction():
    with pytest.raises(TokenError):
        _service(secret="")


def test_unsupported_algorithm_is_refused_at_construction():
    for algorithm in ("HS512", "RS256", "none", "HS384"):
        with pytest.raises(TokenError):
            _service(algorithm=algorithm)


def test_expired_access_token_is_rejected():
    expired = TokenService(SECRET, "HS256", -1, 7)
    token = expired.create_access_token("user-1", UserRole.CUSTOMER)
    with pytest.raises(TokenError):
        _service().decode(token, "access")


def test_token_signed_with_other_secret_is_rejected():
    attacker = _service(secret="another-secret-that-is-at-least-32-long")
    token = attacker.create_access_token("victim", UserRole.ADMIN)
    with pytest.raises(TokenError):
        _service().decode(token, "access")


def test_alg_none_forgery_is_rejected():
    """A forged unsigned token must never decode, whatever claims it carries."""
    import time

    claims = {
        "sub": "attacker",
        "role": UserRole.ADMIN.value,
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
    }
    forged = pyjwt.encode(claims, key=None, algorithm="none")
    with pytest.raises(TokenError):
        _service().decode(forged, "access")


def test_refresh_token_cannot_be_used_as_access_token():
    token = _service().create_refresh_token("user-1", UserRole.CUSTOMER)
    with pytest.raises(TokenError):
        _service().decode(token, "access")


def test_access_token_cannot_be_used_as_refresh_token():
    token = _service().create_access_token("user-1", UserRole.CUSTOMER)
    with pytest.raises(TokenError):
        _service().decode(token, "refresh")
