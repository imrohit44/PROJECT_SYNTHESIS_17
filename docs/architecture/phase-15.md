# Phase 15 — Real-Time Banking Communication

Phase 15 adds **real-time delivery** and **event-driven notifications** on top of
the Phase 0–14 architecture. It deliberately adds **no new service, no new
database, and no new Kafka cluster**.

The whole phase rests on one distinction:

> **Kafka is how components talk. WebSockets are how the browser is told.
> WhatsApp is how a human outside the app is told.**

None of the three is a source of truth. `PostgreSQL` is.

---

## 1. Architecture

```
                    Banking Service
                          │
                          ▼
                     PostgreSQL
                          │
                        Outbox
                          │
                          ▼
                        Kafka  (pybank.events)
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
   Realtime Consumer            Fraud Service
   (pybank-realtime-consumer)   (pybank-fraud-consumer)
            │                     Rules + ML + Neo4j
            │                           │
            │                     risk.assessed
            │                           │
            └─────────────┬─────────────┘
                          ▼
               Notification routing
              (event → Notification objects)
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
     WebSocketChannel             WhatsAppChannel
            │                           │
            ▼                           ▼
      WebSocketManager           WhatsAppProvider
            │                    (outbound only)
            ▼                           │
      Authenticated                        ▼
      React browser                    WhatsApp
```

There is deliberately **no** `Banking → WebSocket` shortcut and **no**
`Banking → WhatsApp` shortcut. Both channels are fed by the same Kafka events
that already existed in Phase 9, so the event-driven design from Phase 9 is
preserved rather than bypassed.

---

## 2. Why the split matters

| Concern | Component | Phase |
|---|---|---|
| Financial truth | PostgreSQL + domain | 0–2 |
| Internal event transport | Kafka | 9 |
| Client delivery | WebSocket | 15 |
| External notification | WhatsApp adapter | 15 |

Keeping these separate means a WebSocket outage, a WhatsApp outage, or a slow
consumer cannot affect whether a transfer actually committed.

---

## 3. WebSocket architecture

### 3.1 Endpoint

`GET /api/v1/ws` (native FastAPI/Starlette WebSocket, no extra service).

### 3.2 Authentication

The socket is **never anonymous**. Authentication reuses the existing Phase 14
JWT model, so there is one identity system in the project.

```
WebSocket  →  JWT  →  Authenticated user  →  Customer  →  Owned accounts
```

The token arrives as a query parameter (`?token=...`) because the browser
`WebSocket` API cannot set an `Authorization` header. This is the standard
compromise for browser WebSockets and is documented as such in
[Known limitations](#12-known-limitations).

Critically, the identity chain is resolved **server-side**. The browser cannot
ask for another customer's data:

```json
{"account_id": "someone-elses-account"}
```

The client sends no subscription payload at all. The server maps
`event → account/customer → authorized user → socket` and pushes. There is no
client-controlled subscription to validate.

Rejection happens **before `accept()`**, so an unauthenticated socket never
becomes a live connection — uvicorn answers the HTTP handshake with `403`.

### 3.3 Connection manager

`backend/app/realtime/manager.py`

```python
class WebSocketManager:
    async def connect(self, user_id: str, websocket: WebSocket) -> None
    def disconnect(self, user_id: str, websocket: WebSocket) -> None
    async def send_to_user(self, user_id, message, *, event_type, correlation_id) -> int
```

Connections are stored per **user id**, not globally, and `send_to_user`
returns how many sockets were reached. A user with three tabs open gets three
deliveries; a user with none is simply *offline*, which is **not** an error.

### 3.4 Message contract

### 3.5 User isolation

This is the critical rule, enforced in `_find_user_id_by_customer` /
`_find_user_id_by_transaction` in `backend/app/notifications/consumer.py`. An
event becomes a `Notification` whose `recipient_user_id` is resolved from the
**database**, then goes to `send_to_user(recipient_user_id, …)`.

There is no broadcast path. A bystander who owns no account involved in a
transfer receives nothing — verified live in `docs/verification/phase-15.md`.

### 3.6 Kafka → WebSocket

`backend/app/notifications/consumer.py` subscribes to `pybank.events` under the
explicit group `pybank-realtime-consumer` and reuses the existing
`ProcessedEvent` idempotency table.

It reuses **existing** events rather than inventing new ones:

| Kafka event | Consumer action |
|---|---|
| `transfer.completed` | notify sender + receiver |
| `risk.assessed` | notify on `HIGH`, informational on `MEDIUM`, silent on `LOW` |

No redundant events were created — `transfer.completed` already existed from
Phase 9, and `risk.assessed` from Phase 13.

---

## 4. Notification architecture

A small adapter model, not an enterprise framework.

```python
class NotificationChannel(Protocol):
    @property
    def channel_name(self) -> str: ...
    async def send(self, notification: Notification) -> bool: ...
```

- `WebSocketChannel` — pushes to the browser.
- `WhatsAppChannel` — resolves the customer's phone from the database, then
  calls the provider.

`NotificationService.dispatch(notification)` runs each channel and records a
bounded `result` label: `success`, `offline`, `disabled`, or `failed`.

The `Notification` model is **channel-neutral**:

```python
(
    event_type,
    recipient_user_id,
    title,
    message,
)
severity, correlation_id, event_id, occurred_at, metadata
```

### 4.1 Event → notification mapping

Mapping is explicit Python. The LLM is **not** used for routing,
authorization, or wording of event notifications — the Phase 14 assistant is a
separate, user-initiated feature.

```
transfer.completed  → "Transfer completed" / "Money received"
risk.assessed HIGH  → "Security Alert"      (severity: high)
risk.assessed MEDIUM→ "Security Notice"     (severity: warning)
risk.assessed LOW   → (no notification)
```

### 4.2 Concise notifications

Notifications stay deliberately terse:

> **Good** — "Your transfer of ₹2,500 was sent."

> **Bad** — "Transfer TX123 used account ID X, Neo4j found 4 counterparties and
> the GradientBoostingClassifier generated probability 0.81."

The second form belongs in an authenticated application view, not a
notification.


---

## 5. WhatsApp adapter

`backend/app/notifications/whatsapp.py`

```python
class WhatsAppProvider(Protocol):
    def send_message(self, recipient_phone, message, *, correlation_id) -> bool
```

The provider sits behind a protocol so the project is **not** hard-wired to one
vendor. The bundled implementation speaks the Meta WhatsApp Cloud API; a
different vendor means a new class, not a rewrite.

**Outbound only.** A reply from a WhatsApp user is never parsed for commands.
There is no inbound webhook, no transfer command, no balance-changing path, no
conversational agent. This boundary is intentional and is what keeps Phase 15
safe.

Configuration is environment-driven and nothing is committed:

```
WHATSAPP_ENABLED=false
WHATSAPP_PROVIDER=cloud_api
WHATSAPP_API_URL=https://graph.facebook.com/v18.0
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_SENDER_ID=
WHATSAPP_TIMEOUT_SECONDS=5
```

The recipient phone number is resolved **from the customer's stored record**,
never from a Kafka payload or LLM input. Phone numbers are never logged, never
used as a metric label, and never shown in the UI.

---

## 6. Delivery semantics

Stated honestly:

- WebSocket delivery is **at-least-once and best-effort**. A user with no open
  socket simply misses the notification. The financial transaction is
  unaffected either way.
- Duplicate notification delivery is possible with Kafka redelivery and is
  **tolerated**; the client keys notifications by `event_id` and renders
  safely. A duplicate notification never modifies a financial transaction.
- Exactly-once **external** WhatsApp delivery is not claimed. Providers may
  retry or reject; responses are handled and failures counted.
- There is no persistent notification queue. Kafka is the transport.

**A WebSocket message is not proof of a committed transaction.** It is derived
from the existing outbox-backed event flow, so it reflects a domain event that
was already persisted — but the socket itself is only a delivery mechanism.

---

---

## 8. Observability

**Metrics** (bounded labels `channel`, `event_type`, `result` only — never
`user_id`, `customer_id`, `account_id`, `transaction_id`, or `phone_number`):

```
realtime_websocket_connections_total      realtime_messages_sent_total
realtime_websocket_disconnects_total      realtime_message_failures_total
notification_dispatch_total               whatsapp_messages_sent_total
notification_dispatch_failures_total      whatsapp_message_failures_total
```

**Tracing** (OpenTelemetry, reusing Phase 11 infrastructure):

```
realtime.kafka_consume → notification.dispatch → realtime.websocket_send
                                                      → notification.whatsapp_send
```

No user data in span attributes.

**Logging** (structlog): `service`, `operation`, `event_type`, `event_id`,
`correlation_id`, `channel`, `result`, `duration_ms`. Never tokens, phone
numbers, JWTs, or full transaction payloads.

**Correlation IDs** flow end to end:

```
HTTP request (X-Correlation-ID) → Kafka event → consumer → WebSocket message
```

Verified live: the correlation ID sent with a transfer request appears on the
browser's WebSocket message.

---

## 9. Frontend

`frontend/src/lib/useRealtime.ts` — a small hook, not a state framework:

- connects with the stored JWT,
- parses the typed envelope,
- reconnects with bounded backoff (1s → 2s → 4s → 8s, capped),
- disconnects cleanly on unmount,
- guards against duplicate connections from React re-renders,
- surfaces `connected | connecting | disconnected`.

The Dashboard shows a live indicator and transient notifications. If the socket
is down, the rest of the dashboard is fully usable.

---

## 10. Security summary

| Concern | Control |
|---|---|
| Anonymous sockets | Rejected before `accept()` (HTTP 403) |
| Client-supplied identity | Not accepted; identity is server-resolved |
| Cross-user leakage | Per-user routing, no broadcast path |
| Payload leakage | `extra="forbid"` envelope, sanitized `data` |
| WhatsApp credentials | Env only, never logged, never sent to React |
| Phone numbers | Never in logs, metrics, traces, or UI |
| Inbound WhatsApp | Not implemented; no command execution path |
| Promised transactions | Documented as notifications, not truth |

---

## 11. Testing

Backend `backend/tests/realtime/` — 15 focused tests covering authentication,
rejection, connection management, user isolation, mapping, severity handling,
channel selection, sensitive-data filtering, correlation propagation, and all
WhatsApp paths (disabled, failure, success, no inbound commands).

Frontend `useRealtime.test.tsx` — 5 tests covering connect, receive, reconnect,
unmount cleanup, and duplicate-connection prevention.

Live verification in `artifacts/phase15/` proves the whole path in Docker.

---

## 12. Known limitations

- **Process-local connection manager.** Sockets live in one process's memory.
  Running multiple Banking replicas would require a shared fan-out (Redis
  Pub/Sub or a dedicated broker) so an event consumed on replica A reaches a
  socket held by replica B. This is **out of scope for Phase 15** and would be
  required before horizontal scaling.
- **Token in query string.** Standard for browser WebSockets, but URLs can be
  logged by proxies. A short-lived, single-use connection ticket would be the
  production hardening.
- **Best-effort delivery.** No durable per-user notification queue; a user
  offline at event time gets no replay.
- **No inbound WhatsApp.** Outbound only, by design.


## 7. Failure behavior

| Failure | Result |
|---|---|
| WebSocket unavailable | Banking continues; the UI stays usable |
| Client disconnects | Server releases the socket; metrics increment |
| Consumer lags / Kafka hiccup | Transaction processing unaffected |
| WhatsApp down | Banking succeeds; failure logged + counted |
| Wrong-user event | Never delivered |

Banking **liveness and readiness do not include** WebSocket or WhatsApp. These
are optional channels, not core dependencies. The notification consumer reports
its own health without gating the service.

WhatsApp failures emit `whatsapp_notification_failed` and increment
`whatsapp_message_failures_total`. Delivery is never silently reported as
successful.


`backend/app/realtime/schemas.py`

```json
{
  "type": "transfer.completed",
  "event_id": "…",
  "occurred_at": "2026-01-01T00:00:00+00:00",
  "correlation_id": "…",
  "data": { "title": "…", "message": "…", "severity": "info" }
}
```

The schema is `extra="forbid"`, and the internal Kafka envelope is **never**
forwarded. The browser never receives: passwords, JWTs, `Authorization`
headers, internal database row ids, raw fraud payloads, Neo4j results, or ML
feature values.
