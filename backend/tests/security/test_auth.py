from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from backend.app.api.dependencies import get_auth, get_bank, get_login_limiter
from backend.app.application.auth import AuthApplicationService
from backend.app.application.banking import BankApplicationService
from backend.app.infrastructure.persistence.database import create_session_factory
from backend.app.infrastructure.persistence.models import Base, UserModel
from backend.app.main import app
from backend.app.security.passwords import PasswordService
from backend.app.security.roles import UserRole
from backend.app.security.tokens import TokenService


@pytest.fixture
def auth_context(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, AuthApplicationService]]:
    database_url = f"sqlite:///{tmp_path / 'auth.sqlite3'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(database_url)
    auth = AuthApplicationService(
        factory,
        PasswordService(),
        TokenService("test-secret-that-is-at-least-32-bytes-long", "HS256", 15, 7),
    )
    app.dependency_overrides[get_auth] = lambda: auth
    app.dependency_overrides[get_bank] = lambda: BankApplicationService(factory)
    get_login_limiter.cache_clear()
    with TestClient(app) as client:
        yield client, auth
    app.dependency_overrides.clear()
    get_login_limiter.cache_clear()


def test_registration_hashes_password_and_login_issues_two_token_types(
    auth_context: tuple[TestClient, AuthApplicationService],
) -> None:
    client, auth = auth_context
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice",
            "email": "Alice@Example.com",
            "password": "correct horse battery staple",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 201
    assert login.status_code == 200
    assert "password" not in response.text
    assert "password_hash" not in response.text
    with auth._session_factory() as session:
        user = session.scalar(select(UserModel))
        assert user is not None
        assert user.password_hash != "correct horse battery staple"
        assert user.password_hash.startswith("$argon2")
        assert PasswordService().verify(
            "correct horse battery staple", user.password_hash
        )
        assert not PasswordService().verify("wrong password", user.password_hash)
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]
    assert auth._tokens.decode(access, "access")["type"] == "access"
    assert auth._tokens.decode(refresh, "refresh")["type"] == "refresh"


def test_invalid_credentials_are_generic_and_inactive_users_cannot_login(
    auth_context: tuple[TestClient, AuthApplicationService],
) -> None:
    client, auth = auth_context
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong password"},
    )
    unknown_user = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong password"},
    )
    with auth._session_factory.begin() as session:
        user = session.scalar(select(UserModel))
        assert user is not None
        user.is_active = False
    inactive = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery staple"},
    )

    assert wrong_password.json() == unknown_user.json()
    assert inactive.status_code == 401


def test_refresh_rejects_access_tokens_and_returns_new_access_token(
    auth_context: tuple[TestClient, AuthApplicationService],
) -> None:
    client, _ = auth_context
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery staple"},
    )
    tokens = login.json()
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    wrong_type = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    assert wrong_type.status_code == 401


def test_malformed_and_expired_access_tokens_are_rejected(
    auth_context: tuple[TestClient, AuthApplicationService],
) -> None:
    client, _ = auth_context
    malformed = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    expired_service = TokenService(
        "test-secret-that-is-at-least-32-bytes-long", "HS256", -1, 7
    )
    expired = expired_service.create_access_token("missing-user", UserRole.CUSTOMER)
    expired_response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )

    assert malformed.status_code == 401
    assert expired_response.status_code == 401


def test_customer_is_rejected_and_admin_is_accepted_for_user_listing(
    auth_context: tuple[TestClient, AuthApplicationService],
) -> None:
    client, auth = auth_context
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery staple"},
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    customer_response = client.get("/api/v1/users")

    with auth._session_factory.begin() as session:
        user = session.scalar(
            select(UserModel).where(UserModel.id == registration.json()["user_id"])
        )
        assert user is not None
        user.role = UserRole.ADMIN.value
    admin_response = client.get("/api/v1/users")

    assert customer_response.status_code == 403
    assert admin_response.status_code == 200
    assert admin_response.json()[0]["role"] == "admin"


def test_login_rate_limit_is_enforced(
    auth_context: tuple[TestClient, AuthApplicationService],
) -> None:
    client, _ = auth_context
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )

    responses = [
        client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "wrong password"},
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses][-1] == 429
