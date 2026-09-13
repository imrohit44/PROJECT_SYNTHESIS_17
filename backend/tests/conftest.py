import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")

from backend.app.api.dependencies import (  # noqa: E402
    get_auth,
    get_bank,
    get_login_limiter,
)
from backend.app.application.auth import AuthApplicationService  # noqa: E402
from backend.app.application.banking import BankApplicationService  # noqa: E402
from backend.app.infrastructure.persistence.database import (  # noqa: E402
    create_session_factory,
)
from backend.app.infrastructure.persistence.models import Base  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.security.passwords import PasswordService  # noqa: E402
from backend.app.security.tokens import TokenService  # noqa: E402


def pytest_collection_modifyitems(
    items: list[pytest.Item],
) -> None:
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/security/" in path:
            item.add_marker(pytest.mark.security)
        if "/persistence/" in path or "/api/" in path:
            item.add_marker(pytest.mark.integration)
        if "/domain/" in path:
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def fake_email(request: pytest.FixtureRequest) -> Iterator[str]:
    """Provide deterministic, test-local email data without shared state."""

    yield f"{request.node.name}@example.test"


@pytest.fixture
def session_factory(tmp_path: Path) -> sessionmaker[Session]:
    database_url = f"sqlite:///{tmp_path / 'pybank-test.sqlite3'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return create_session_factory(database_url)


@pytest.fixture
def bank_service(session_factory: sessionmaker[Session]) -> BankApplicationService:
    return BankApplicationService(session_factory)


@pytest.fixture
def auth_service(session_factory: sessionmaker[Session]) -> AuthApplicationService:
    return AuthApplicationService(
        session_factory,
        PasswordService(),
        TokenService("test-secret-that-is-at-least-32-bytes-long", "HS256", 15, 7),
    )


@pytest.fixture
def client(
    bank_service: BankApplicationService,
    auth_service: AuthApplicationService,
) -> Iterator[TestClient]:
    app.dependency_overrides[get_bank] = lambda: bank_service
    app.dependency_overrides[get_auth] = lambda: auth_service
    get_login_limiter.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_login_limiter.cache_clear()


@pytest.fixture
def user_factory(client: TestClient) -> Callable[..., dict[str, str]]:
    def create_user(
        *,
        name: str = "Alice",
        email: str | None = None,
        password: str = "correct horse battery staple",
    ) -> dict[str, str]:
        user_email = email or f"{name.lower()}@example.com"
        response = client.post(
            "/api/v1/auth/register",
            json={"name": name, "email": user_email, "password": password},
        )
        assert response.status_code == 201
        body = response.json()
        return {
            "user_id": body["user_id"],
            "customer_id": body["customer_id"],
            "email": user_email,
            "password": password,
        }

    return create_user


@pytest.fixture
def token_factory(
    client: TestClient,
    user_factory: Callable[..., dict[str, str]],
) -> Callable[..., dict[str, str]]:
    def issue_token(**overrides: str) -> dict[str, str]:
        user = user_factory(**overrides)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": user["password"]},
        )
        assert response.status_code == 200
        return {**user, **response.json()}

    return issue_token


@pytest.fixture
def auth_headers(token_factory: Callable[..., dict[str, str]]) -> dict[str, str]:
    tokens = token_factory()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def postgres_session_factory() -> Iterator[sessionmaker[Session]]:
    database_url = os.environ.get("PYBANK_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("PYBANK_TEST_DATABASE_URL is required for PostgreSQL tests")
    if "pybank" not in database_url.lower() or "test" not in database_url.lower():
        pytest.fail("Refusing to run PostgreSQL tests without a clearly named test DB")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        Base.metadata.create_all(connection)
    yield create_session_factory(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
