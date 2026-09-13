from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.application.auth import AuthApplicationService
from backend.app.infrastructure.persistence.models import UserModel
from backend.app.security.roles import UserRole


def register(client: TestClient, name: str = "Alice") -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": name,
            "email": f"{name.lower()}@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    body = response.json()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"{name.lower()}@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert login.status_code == 200
    return body["customer_id"], login.json()["access_token"]


def use_token(client: TestClient, token: str) -> None:
    client.headers["Authorization"] = f"Bearer {token}"


def test_health_and_security_headers_are_public(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_create_and_retrieve_customer(client: TestClient) -> None:
    customer_id, token = register(client)
    use_token(client, token)

    response = client.get(f"/api/v1/customers/{customer_id}")

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
    assert "password_hash" not in response.text


def test_account_deposit_withdraw_and_history(client: TestClient) -> None:
    customer_id, token = register(client)
    use_token(client, token)
    account = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": customer_id,
            "account_type": "savings",
            "opening_balance": "100.00",
        },
    )
    account_id = account.json()["account_id"]

    deposit = client.post(
        f"/api/v1/accounts/{account_id}/deposit", json={"amount": "25.00"}
    )
    withdraw = client.post(
        f"/api/v1/accounts/{account_id}/withdraw", json={"amount": "10.00"}
    )
    history = client.get(f"/api/v1/accounts/{account_id}/transactions")

    assert account.status_code == 201
    assert deposit.status_code == 200
    assert withdraw.status_code == 200
    assert withdraw.json()["balance"] == "115.00"
    assert history.status_code == 200
    assert len(client.get("/api/v1/accounts").json()) == 1


def test_cross_customer_account_access_is_forbidden(client: TestClient) -> None:
    _, alice_token = register(client, "Alice")
    bob_id, bob_token = register(client, "Bob")
    use_token(client, bob_token)
    account_id = client.post(
        "/api/v1/accounts",
        json={"customer_id": bob_id, "account_type": "savings"},
    ).json()["account_id"]

    use_token(client, alice_token)
    response = client.get(f"/api/v1/accounts/{account_id}")

    assert response.status_code == 403


def test_transfer_requires_source_ownership(client: TestClient) -> None:
    alice_id, alice_token = register(client, "Alice")
    bob_id, bob_token = register(client, "Bob")
    use_token(client, alice_token)
    source_id = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": alice_id,
            "account_type": "current",
            "opening_balance": "100.00",
            "overdraft_limit": "50.00",
        },
    ).json()["account_id"]
    use_token(client, bob_token)
    destination_id = client.post(
        "/api/v1/accounts",
        json={"customer_id": bob_id, "account_type": "savings"},
    ).json()["account_id"]

    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source_id,
            "destination_account_id": destination_id,
            "amount": "10.00",
        },
    )

    assert response.status_code == 403


def test_invalid_amount_and_insufficient_funds_are_mapped(client: TestClient) -> None:
    customer_id, token = register(client)
    use_token(client, token)
    account_id = client.post(
        "/api/v1/accounts",
        json={"customer_id": customer_id, "account_type": "savings"},
    ).json()["account_id"]

    invalid = client.post(
        f"/api/v1/accounts/{account_id}/deposit", json={"amount": "0"}
    )
    insufficient = client.post(
        f"/api/v1/accounts/{account_id}/withdraw", json={"amount": "1.00"}
    )

    assert invalid.status_code == 422
    assert insufficient.status_code == 409


def test_authentication_and_admin_protection(client: TestClient) -> None:
    _, token = register(client)
    use_token(client, token)
    admin_response = client.get("/api/v1/users")
    client.headers.pop("Authorization")
    missing_response = client.get("/api/v1/users")

    assert admin_response.status_code == 403
    assert missing_response.status_code == 401


def test_duplicate_registration_and_invalid_login_are_safe(client: TestClient) -> None:
    register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Other",
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )
    invalid_login = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong password"},
    )

    assert duplicate.status_code == 409
    assert invalid_login.status_code == 401
    assert invalid_login.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_refresh_me_and_successful_transfer_contract(client: TestClient) -> None:
    alice_id, alice_token = register(client, "Alice")
    bob_id, bob_token = register(client, "Bob")
    use_token(client, alice_token)
    source_id = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": alice_id,
            "account_type": "current",
            "opening_balance": "100.00",
            "overdraft_limit": "50.00",
        },
    ).json()["account_id"]
    use_token(client, bob_token)
    destination_id = client.post(
        "/api/v1/accounts",
        json={"customer_id": bob_id, "account_type": "savings"},
    ).json()["account_id"]
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )
    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    use_token(client, refresh.json()["access_token"])

    me = client.get("/api/v1/auth/me")
    transfer = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source_id,
            "destination_account_id": destination_id,
            "amount": "40.00",
        },
    )
    source = client.get(f"/api/v1/accounts/{source_id}")

    assert refresh.status_code == 200
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"
    assert "password_hash" not in me.text
    assert transfer.status_code == 200
    assert transfer.json()["amount"] == "40.00"
    assert source.json()["balance"] == "60.00"


def test_admin_can_create_customer_and_list_users(
    client: TestClient,
    auth_service: AuthApplicationService,
) -> None:
    _, token = register(client)
    with auth_service._session_factory.begin() as session:
        user = session.scalar(select(UserModel))
        assert user is not None
        user.role = UserRole.ADMIN.value
    use_token(client, token)

    created = client.post(
        "/api/v1/customers",
        json={"name": "Carol", "email": "carol@example.com"},
    )
    users = client.get("/api/v1/users")

    assert created.status_code == 201
    assert users.status_code == 200
    assert "password_hash" not in users.text


def test_api_error_contract_for_common_status_codes(client: TestClient) -> None:
    customer_id, token = register(client)
    use_token(client, token)

    not_found = client.get("/api/v1/accounts/missing-account")
    validation = client.post(
        "/api/v1/accounts",
        json={"customer_id": customer_id, "account_type": "unknown"},
    )
    conflict = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice Again",
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )

    for response in (not_found, validation, conflict):
        body = response.json()
        assert set(body) == {"error"}
        assert {"code", "message"} <= set(body["error"])
    assert not_found.status_code == 404
    assert validation.status_code == 422
    assert conflict.status_code == 409
