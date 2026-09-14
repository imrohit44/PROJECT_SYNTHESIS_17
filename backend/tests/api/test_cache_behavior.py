from typing import Any

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_cache
from backend.app.main import app


class MemoryCache:
    def __init__(self, fail: bool = False) -> None:
        self.values: dict[str, Any] = {}
        self.sets: list[str] = []
        self.deletes: list[tuple[str, ...]] = []
        self.fail = fail

    def get_json(self, key: str) -> Any | None:
        if self.fail:
            return None
        return self.values.get(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.sets.append(key)
        if not self.fail:
            self.values[key] = value

    def delete(self, *keys: str) -> None:
        self.deletes.append(keys)
        if not self.fail:
            for key in keys:
                self.values.pop(key, None)


def _register_and_login(client: TestClient) -> tuple[str, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Cache User",
            "email": "cache@example.com",
            "password": "correct horse battery staple",
        },
    )
    customer_id = response.json()["customer_id"]
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "cache@example.com",
            "password": "correct horse battery staple",
        },
    )
    return customer_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_account_cache_aside_and_invalidation(client: TestClient) -> None:
    cache = MemoryCache()
    app.dependency_overrides[get_cache] = lambda: cache
    customer_id, headers = _register_and_login(client)
    account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"customer_id": customer_id, "account_type": "savings"},
    ).json()

    first = client.get(f"/api/v1/accounts/{account['account_id']}", headers=headers)
    second = client.get(f"/api/v1/accounts/{account['account_id']}", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert cache.sets == [f"account:{account['account_id']}"]

    deposit = client.post(
        f"/api/v1/accounts/{account['account_id']}/deposit",
        headers=headers,
        json={"amount": "10.00"},
    )

    assert deposit.status_code == 200
    expected_keys = (
        f"account:{account['account_id']}",
        f"customer:{customer_id}:accounts",
    )
    assert expected_keys in cache.deletes


def test_failed_withdraw_does_not_invalidate_cache(client: TestClient) -> None:
    cache = MemoryCache()
    app.dependency_overrides[get_cache] = lambda: cache
    customer_id, headers = _register_and_login(client)
    account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"customer_id": customer_id, "account_type": "savings"},
    ).json()
    cache.deletes.clear()

    response = client.post(
        f"/api/v1/accounts/{account['account_id']}/withdraw",
        headers=headers,
        json={"amount": "1.00"},
    )

    assert response.status_code == 409
    assert cache.deletes == []


def test_cache_unavailable_falls_back_to_database(client: TestClient) -> None:
    cache = MemoryCache(fail=True)
    app.dependency_overrides[get_cache] = lambda: cache
    customer_id, headers = _register_and_login(client)

    response = client.get(f"/api/v1/customers/{customer_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "cache@example.com"
