"""Notification channels and orchestration service.

Channels deliver channel-neutral Notification objects:
- WebSocketChannel: Delivers typed events to connected browsers.
- WhatsAppChannel: Delivers text alerts via the WhatsApp provider.
"""

from __future__ import annotations

import structlog
from sqlalchemy.orm import Session, sessionmaker

from backend.app.infrastructure.metrics import (
    NOTIFICATION_DISPATCH_FAILURES_TOTAL,
    NOTIFICATION_DISPATCH_TOTAL,
)
from backend.app.infrastructure.persistence.models import CustomerModel, UserModel
from backend.app.notifications.models import Notification, NotificationChannel
from backend.app.notifications.whatsapp import WhatsAppProvider
from backend.app.realtime.manager import WebSocketManager, get_websocket_manager
from backend.app.realtime.schemas import RealtimeMessage
from services.common.tracing import get_tracer

logger = structlog.get_logger(__name__)


class WebSocketChannel(NotificationChannel):
    """Notification channel routing alerts to browser WebSockets."""

    def __init__(self, manager: WebSocketManager | None = None) -> None:
        self._manager = manager or get_websocket_manager()

    @property
    def channel_name(self) -> str:
        return "websocket"

    async def send(self, notification: Notification) -> bool:
        """Return True when the notification reached at least one recipient.

        A user with no open browser socket is *not* a failure: there was
        simply nobody online to tell. Genuine send errors are already
        counted by the manager's ``realtime_message_failures_total``.
        """
        message = RealtimeMessage(
            type=notification.event_type,
            event_id=notification.event_id,
            occurred_at=notification.occurred_at,
            correlation_id=notification.correlation_id,
            data={
                "title": notification.title,
                "message": notification.message,
                "severity": notification.severity,
                **notification.metadata,
            },
        )
        delivered = await self._manager.send_to_user(
            user_id=notification.recipient_user_id,
            message=message.model_dump(),
            event_type=notification.event_type,
            correlation_id=notification.correlation_id,
        )
        return delivered > 0


class WhatsAppChannel(NotificationChannel):
    """Notification channel routing alerts to WhatsApp."""

    def __init__(
        self,
        provider: WhatsAppProvider,
        session_factory: sessionmaker[Session],
        enabled: bool = True,
    ) -> None:
        self._provider = provider
        self._session_factory = session_factory
        self._enabled = enabled

    @property
    def channel_name(self) -> str:
        return "whatsapp"

    @property
    def enabled(self) -> bool:
        """Whether this channel is enabled and configured for delivery."""
        return self._enabled

    async def send(self, notification: Notification) -> bool:
        if not self._enabled:
            return False

        # Look up customer's verified phone number from DB
        recipient_phone = self._lookup_recipient_phone(notification.recipient_user_id)
        if not recipient_phone:
            logger.debug(
                "whatsapp_recipient_no_phone",
                recipient_user_id=notification.recipient_user_id,
            )
            return False

        body = f"{notification.title}\n{notification.message}"
        return await self._provider.send_message(
            recipient_phone=recipient_phone,
            message=body,
            correlation_id=notification.correlation_id,
        )

    def _lookup_recipient_phone(self, user_id: str) -> str | None:
        """Resolve recipient user ID to customer's stored phone number."""
        with self._session_factory() as session:
            user = session.get(UserModel, user_id)
            if user is None:
                return None
            customer = session.get(CustomerModel, user.customer_id)
            if customer is None or not customer.phone:
                return None
            return customer.phone.strip()


class NotificationService:
    """Dispatches notifications across configured channels."""

    def __init__(self, channels: list[NotificationChannel]) -> None:
        self._channels = channels
        # A channel is "configured" when it is not a permanently disabled
        # WhatsApp channel. Used to label disabled-vs-failed honestly.
        self._whatsapp_configured = any(
            isinstance(channel, WhatsAppChannel) and channel.enabled
            for channel in channels
        )

    async def dispatch(self, notification: Notification) -> dict[str, bool]:
        """Send notification to all channels.

        High severity alerts trigger all available channels.
        Normal/info notifications may target selected channels.
        """
        tracer = get_tracer(__name__)
        results: dict[str, bool] = {}

        with tracer.start_as_current_span("notification.dispatch") as span:
            span.set_attribute("event_type", notification.event_type)
            span.set_attribute("severity", notification.severity)
            if notification.correlation_id:
                span.set_attribute("correlation_id", notification.correlation_id)

            for channel in self._channels:
                ch_name = channel.channel_name
                # WhatsApp only for warning/high, except completed transfers.
                if (
                    ch_name == "whatsapp"
                    and notification.severity == "info"
                    and notification.event_type != "transfer.completed"
                ):
                    continue

                try:
                    success = await channel.send(notification)
                    results[ch_name] = success
                    # Honest labels: a user with no open socket is "offline",
                    # not a failure. True failures are counted separately by
                    # the channel (realtime_message_failures_total /
                    # whatsapp_message_failures_total) and by the counter below.
                    if success:
                        result_label = "success"
                    elif ch_name == "whatsapp" and not self._whatsapp_configured:
                        result_label = "disabled"
                    elif ch_name == "websocket":
                        result_label = "offline"
                    else:
                        result_label = "failed"
                    NOTIFICATION_DISPATCH_TOTAL.labels(
                        channel=ch_name,
                        event_type=notification.event_type,
                        result=result_label,
                    ).inc()
                    if not success and result_label == "failed":
                        NOTIFICATION_DISPATCH_FAILURES_TOTAL.labels(
                            channel=ch_name,
                            event_type=notification.event_type,
                        ).inc()
                    logger.info(
                        "notification_dispatched",
                        channel=ch_name,
                        event_type=notification.event_type,
                        event_id=notification.event_id,
                        correlation_id=notification.correlation_id,
                        severity=notification.severity,
                        result=result_label,
                    )
                except Exception as error:
                    results[ch_name] = False
                    NOTIFICATION_DISPATCH_FAILURES_TOTAL.labels(
                        channel=ch_name,
                        event_type=notification.event_type,
                    ).inc()
                    NOTIFICATION_DISPATCH_TOTAL.labels(
                        channel=ch_name,
                        event_type=notification.event_type,
                        result="failed",
                    ).inc()
                    logger.warning(
                        "notification_channel_failed",
                        channel=ch_name,
                        event_type=notification.event_type,
                        error=str(error),
                    )

            return results
