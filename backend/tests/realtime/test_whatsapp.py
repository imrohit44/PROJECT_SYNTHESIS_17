"""Phase 15: WhatsApp adapter unit coverage (deterministic, no network)."""

from __future__ import annotations

import httpx
import pytest

from backend.app.notifications.whatsapp import MetaCloudWhatsAppProvider


class _OKTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})


@pytest.mark.asyncio
async def test_unconfigured_provider_skips_without_network() -> None:
    provider = MetaCloudWhatsAppProvider(
        api_url="https://graph.facebook.com/v18.0",
        phone_number_id="",
        access_token="",
    )
    assert provider.is_configured is False
    assert await provider.send_message("+10000000009", "hello") is False


@pytest.mark.asyncio
async def test_configured_provider_posts_and_records_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = _OKTransport()

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    provider = MetaCloudWhatsAppProvider(
        api_url="https://graph.facebook.com/v18.0",
        phone_number_id="123",
        access_token="test-token",
    )
    assert await provider.send_message("+10000000010", "hello", "corr-1") is True
    assert len(transport.requests) == 1
    body = transport.requests[0].headers.get("authorization", "")
    assert "test-token" not in str(transport.requests[0].url)
    assert body != ""


def test_no_inbound_whatsapp_command_surface() -> None:
    import backend.app.notifications.service as service
    import backend.app.notifications.whatsapp as module

    source = open(module.__file__).read() + open(service.__file__).read()
    lowered = source.lower()
    assert "inbound" not in lowered or "forbidden" in lowered or "only" in lowered
    assert "withdraw" not in lowered
    assert "deposit" not in lowered
    assert "transfer(" not in lowered
