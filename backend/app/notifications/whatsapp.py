"""Outbound WhatsApp provider abstraction and Meta Cloud API implementation.

Security and architectural boundaries:
- Outbound notifications ONLY.
- Inbound banking commands or messages are strictly forbidden.
- Phone numbers and access tokens are NEVER logged or exported to Prometheus labels.
- If unconfigured or failing, banking and Kafka flows remain completely unaffected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
import structlog

from backend.app.infrastructure.metrics import (
    WHATSAPP_MESSAGE_FAILURES_TOTAL,
    WHATSAPP_MESSAGES_SENT_TOTAL,
)
from services.common.tracing import get_tracer

logger = structlog.get_logger(__name__)


class WhatsAppProvider(ABC):
    """Abstract outbound WhatsApp messaging provider."""

    @abstractmethod
    async def send_message(
        self,
        recipient_phone: str,
        message: str,
        correlation_id: str | None = None,
    ) -> bool:
        """Send an outbound text message to a phone number. Return True on success."""
        ...


class MetaCloudWhatsAppProvider(WhatsAppProvider):
    """Official Meta Cloud API WhatsApp provider implementation."""

    def __init__(
        self,
        api_url: str,
        phone_number_id: str,
        access_token: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._timeout = timeout_seconds

    @property
    def is_configured(self) -> bool:
        """Return True if credentials and phone number ID are configured."""
        return bool(self._access_token and self._phone_number_id)

    async def send_message(
        self,
        recipient_phone: str,
        message: str,
        correlation_id: str | None = None,
    ) -> bool:
        """Send a message via WhatsApp Cloud API."""
        if not self.is_configured:
            logger.debug("whatsapp_not_configured_skipping")
            return False

        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("notification.whatsapp_send") as span:
            span.set_attribute("provider", "meta_cloud")
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)

            url = f"{self._api_url}/{self._phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient_phone,
                "type": "text",
                "text": {"preview_url": False, "body": message},
            }

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code in (200, 201):
                    WHATSAPP_MESSAGES_SENT_TOTAL.labels(result="success").inc()
                    logger.info(
                        "whatsapp_notification_sent",
                        provider="meta_cloud",
                        status_code=resp.status_code,
                    )
                    return True
                else:
                    WHATSAPP_MESSAGE_FAILURES_TOTAL.labels(result="api_error").inc()
                    logger.warning(
                        "whatsapp_notification_failed",
                        provider="meta_cloud",
                        status_code=resp.status_code,
                        # NEVER log access token or phone number
                    )
                    return False
            except Exception as error:
                WHATSAPP_MESSAGE_FAILURES_TOTAL.labels(result="network_error").inc()
                logger.warning(
                    "whatsapp_notification_failed",
                    provider="meta_cloud",
                    error=str(error),
                )
                return False
