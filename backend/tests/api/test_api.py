from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_bank
from backend.app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    get_bank.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_bank.cache_clear()


def create_customer(client: TestClient, name: str = "Alice") -> str:
    response = client.post(
        "/api/v1/customers",
        json={"name": name, "email": f"{name.lower()}@example.com"},
    )
    assert response.status_code == 201
    return response.json()["customer_id"]


def test_create_and_retrieve_customer(client: TestClient) -> None:
    customer_id = create_customer(client)

    response = client.get(f"/api/v1/customers/{customer_id}")

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_customer_not_found_has_consistent_error(client: TestClient) -> None:
    response = client.get("/api/v1/customers/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


def test_account_deposit_withdraw_and_history(client: TestClient) -> None:
    customer_id = create_customer(client)
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
    assert [item["transaction_type"] for item in history.json()] == [
        "deposit",
        "withdrawal",
    ]


def test_current_account_and_transfer(client: TestClient) -> None:
    source_customer_id = create_customer(client, "Alice")
    destination_customer_id = create_customer(client, "Bob")
    source = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": source_customer_id,
            "account_type": "current",
            "opening_balance": "100.00",
            "overdraft_limit": "50.00",
        },
    ).json()
    destination = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": destination_customer_id,
            "account_type": "savings",
        },
    ).json()

    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source["account_id"],
            "destination_account_id": destination["account_id"],
            "amount": "125.00",
        },
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "125.00"
    assert (
        client.get(f"/api/v1/accounts/{source['account_id']}").json()["balance"]
        == "-25.00"
    )
    assert (
        client.get(f"/api/v1/accounts/{destination['account_id']}").json()["balance"]
        == "125.00"
    )


def test_invalid_amount_and_insufficient_funds_are_mapped(client: TestClient) -> None:
    customer_id = create_customer(client)
    account_id = client.post(
        "/api/v1/accounts",
        json={"customer_id": customer_id, "account_type": "savings"},
    ).json()["account_id"]

    invalid = client.post(
        f"/api/v1/accounts/{account_id}/deposit", json={"amount": "0"}
    )
    float_amount = client.post(
        f"/api/v1/accounts/{account_id}/deposit", json={"amount": 0.1}
    )
    insufficient = client.post(
        f"/api/v1/accounts/{account_id}/withdraw", json={"amount": "1.00"}
    )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_AMOUNT"
    assert float_amount.status_code == 422
    assert float_amount.json()["error"]["code"] == "VALIDATION_ERROR"
    assert insufficient.status_code == 409
    assert insufficient.json()["error"]["code"] == "INSUFFICIENT_FUNDS"


def test_invalid_account_and_same_account_transfer(client: TestClient) -> None:
    missing = client.get("/api/v1/accounts/missing")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"

    customer_id = create_customer(client)
    account_id = client.post(
        "/api/v1/accounts",
        json={"customer_id": customer_id, "account_type": "savings"},
    ).json()["account_id"]
    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": account_id,
            "destination_account_id": account_id,
            "amount": "1.00",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_TRANSFER"


def test_frozen_and_closed_accounts_map_to_conflict(client: TestClient) -> None:
    customer_id = create_customer(client)
    account_id = client.post(
        "/api/v1/accounts",
        json={"customer_id": customer_id, "account_type": "savings"},
    ).json()["account_id"]
    account = get_bank().find_account(account_id)
    account.freeze()

    frozen = client.post(
        f"/api/v1/accounts/{account_id}/deposit", json={"amount": "1.00"}
    )

    account.activate()
    account.close()
    closed = client.post(
        f"/api/v1/accounts/{account_id}/deposit", json={"amount": "1.00"}
    )

    assert frozen.status_code == 409
    assert frozen.json()["error"]["code"] == "ACCOUNT_NOT_ACTIVE"
    assert closed.status_code == 409
    assert closed.json()["error"]["code"] == "ACCOUNT_NOT_ACTIVE"
