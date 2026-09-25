"""WebSocket endpoint for real-time banking updates.

Authentication is strictly required. A browser cannot set an ``Authorization``
header on a WebSocket handshake, so the client first exchanges its JWT for a
short-lived single-use ticket over normal HTTP (``POST /ws/ticket``) and then
connects with only that opaque ticket.

The raw JWT is deliberately never accepted in the query string: full URLs are
written to uvicorn/proxy access logs, which would leak a long-lived bearer
token. A ticket carries no claims, expires in seconds, and is destroyed on
first use.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from backend.app.api.auth_dependencies import get_current_user
from backend.app.api.dependencies import get_auth
from backend.app.application.auth import AuthApplicationService, AuthenticationError
from backend.app.core.config import get_settings
from backend.app.realtime.manager import WebSocketManager, get_websocket_manager
from backend.app.realtime.tickets import get_ticket_store
from backend.app.security.audit import security_event
from backend.app.security.principal import CurrentUser

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["realtime"])


class WebSocketTicketResponse(BaseModel):
    """Short-lived ticket used to authenticate exactly one WebSocket handshake."""

    ticket: str
    expires_in: int


@router.post("/ws/ticket", response_model=WebSocketTicketResponse)
async def issue_websocket_ticket(
    current_user: CurrentUser = Depends(get_current_user),
) -> WebSocketTicketResponse:
    """Exchange a valid JWT for a short-lived, single-use WebSocket ticket.

    This is an ordinary authenticated HTTP request, so the JWT travels in the
    ``Authorization`` header and is never written to a URL or access log.
    """
    settings = get_settings()
    ticket = get_ticket_store().issue(current_user.user_id)
    logger.info("websocket_ticket_issued", user_id=current_user.user_id)
    return WebSocketTicketResponse(
        ticket=ticket, expires_in=settings.websocket_ticket_ttl_seconds
    )


def _resolve_auth(
    websocket: WebSocket,
    auth_override: AuthApplicationService | None = None,
    manager_override: WebSocketManager | None = None,
) -> tuple[AuthApplicationService, WebSocketManager]:
    """Resolve auth/manager dependencies with test overrides when provided.

    Production path uses the cached FastAPI dependencies. WebSocket routes
    cannot use ``Depends()`` for the ``WebSocket`` parameter itself, so tests
    supply overrides through ``app.dependency_overrides`` keyed by these
    helper functions.
    """
    auth_service = auth_override
    ws_manager = manager_override
    if auth_service is None:
        override = websocket.app.dependency_overrides.get(get_auth)
        auth_service = override() if override is not None else get_auth()
    if ws_manager is None:
        override = websocket.app.dependency_overrides.get(get_websocket_manager)
        ws_manager = override() if override is not None else get_websocket_manager()
    return auth_service, ws_manager


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ticket: str | None = Query(default=None),
) -> None:
    """Authenticated WebSocket connection endpoint.

    Identity is established solely from a verified, unredeemed ticket that was
    issued to an authenticated principal. Clients may not claim identity via
    client-side messages.
    """
    auth_service, ws_manager = _resolve_auth(websocket)

    if not ticket:
        security_event("websocket_unauthorized_attempt")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Single-use: a ticket is burned here whether or not it turns out to be
    # valid, so it can never be replayed for a second connection.
    try:
        user_id = get_ticket_store().consume(ticket)
    except Exception as error:  # pragma: no cover - defensive
        logger.warning("websocket_ticket_consume_error", error=str(error))
        user_id = None

    if not user_id:
        security_event("websocket_authentication_failure")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        current_user = auth_service.get_current_user(user_id)
    except (AuthenticationError, KeyError, TypeError):
        security_event("websocket_authentication_failure")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Connection authenticated successfully
    await ws_manager.connect(current_user.user_id, websocket)

    # Only registered users with an active account relationship receive
    # update streams. The manager itself stays user-keyed, so isolation is
    # enforced at the routing/dispatch layer as well.
    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connection.established",
                "event_id": f"conn-{current_user.user_id}",
                "data": {"customer_id": current_user.customer_id},
            }
        )
        # Keep connection open and listen for client heartbeats or close
        while True:
            # WebSockets in Phase 15 are outbound-notification only.
            # Inbound messages are ignored or used for ping/pong keepalives.
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as error:
        logger.warning(
            "websocket_connection_error",
            user_id=current_user.user_id,
            error=str(error),
        )
    finally:
        await ws_manager.disconnect(current_user.user_id, websocket)
