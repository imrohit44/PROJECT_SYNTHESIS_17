# Phase 15 — Learning Notes

## 1. What is a WebSocket?

An HTTP connection answers **one** request with **one** response and then
closes. A WebSocket starts as an ordinary HTTP request, is *upgraded*, and then
stays open. Both ends can push messages at any time without new connection
overhead.

Think of HTTP as a phone call you hang up after one sentence, and a WebSocket
as a line that stays open both ways.

## 2. Request/response vs WebSockets

| | HTTP (REST) | WebSocket |
|---|---|---|
| Direction | Client asks, server answers | Either side, any time |
| Lifecycle | One request → one response | Long-lived, bidirectional |
| Overhead per message | New connection / headers | Near-zero after upgrade |
| Fits | "What is my balance?" | "Your transfer just landed" |

PyBank already used HTTP correctly: the dashboard asked "what are my
transactions?" and got an answer. The problem is **polling** — asking again
every few seconds wastes requests, adds load, and still shows stale data for
most of the interval.

## 3. Why WebSockets suit a real-time banking UI

When a transfer completes, the balance and activity list on screen are wrong
until refresh. A WebSocket lets the server *push* the moment it happens:

```
Transaction → PostgreSQL → Outbox → Kafka → consumer → WebSocket → React
```

The user sees the new balance without pressing anything. Polling would show the
same result up to N seconds late, forever, at a constant cost.

## 4. Kafka vs WebSockets — the key distinction

This is the central idea of the phase.

**Kafka** is *internal* asynchronous transport between system components. The
Fraud service does not talk to the frontend. It publishes `risk.assessed` and
moves on, whether or not anyone is listening.

**WebSocket** is a *persistent channel between the backend and one connected
client*. It exists for exactly one browser tab and disappears when that tab
closes.

| | Kafka | WebSocket |
|---|---|---|
| Connects | services | backend ↔ one browser |
| Lifetime | persistent | while the tab is open |
| Fan-out | many subscribers | one socket |
| Stores history | yes (retention) | no |
| Survives client restart | events wait in the topic | nothing — the event is gone |
| Audience | internal systems | one human |

Neither can replace the other. Kafka has no idea a browser exists; a WebSocket
has no idea about retries, offsets, or other services.

**A WebSocket message is a delivery, not a receipt.** If the tab was closed, the
message is gone — it is not queued for later.

## 5. Event-driven notifications

Instead of the banking code asking "should I text Alice?", it announces a fact:

```
transfer.completed → { Alice is the source, ₹2,500 }
```

A consumer decides what that means for whom. This is *push to a rule*, not
*push to a hard-coded recipient*.

It matters because the alternative — `if user == "Alice": notify()` inside the
transfer service — couples the financial core to the notification channel. Add
WhatsApp, and you edit transaction processing. Add email, and you edit it again.
With events, new channels consume without touching banking.

## 6. What is an adapter pattern?

An adapter wraps one interface behind another so callers do not depend on the
concrete thing.

```python
class WhatsAppProvider(Protocol):
    def send_message(self, recipient_phone, message, *, correlation_id) -> bool
```

The notification layer knows only this interface. Meta Cloud API, Twilio, or a
fake in tests are interchangeable. Swapping vendors means one new class, not a
rewrite.

The same idea gives us one `NotificationChannel` interface with a WebSocket
implementation and a WhatsApp implementation, so adding SMS later does not
change the service.

## 7. Why WhatsApp is an external channel

WhatsApp is a **third-party service outside our trust boundary**. Messages leave
our infrastructure, pass through Meta's API, and land on someone's personal
phone. That makes it categorically different from WebSockets, which terminate
inside our own authenticated session.

Practically, it means: no user identity of our own on the far end, delivery we
do not control, an external availability dependency, and a real cost. It is an
*external* notification, not an internal transport — exactly like sending an
email, not like a database query.


## 8. Why outbound-only WhatsApp is safer for this phase

Inbound WhatsApp means accepting untrusted free text from anyone, mapping it to
intent, and executing money movement. That means: message authentication,
replay protection, ambiguity handling, strong confirmation for irreversible
actions, and a much larger attack surface.

Phase 15 sends **outbound only**. A reply like "send ₹5000 to Rahul" is simply
never interpreted — no such code path exists, and there is a test asserting it.
The same safety logic is why real banks put a mandatory step between "inbound
instruction" and "money moves".

Deferring inbound is a scope decision, not a capability gap.

## 9. Notification delivery ≠ transaction processing

The transaction is the money movement: validate, lock rows, write, commit, emit
an event. It is correct because PostgreSQL committed it.

The notification is *"tell someone it happened"*. It can fail, duplicate, be
late, or never arrive, and the money is still moved.

Blurring these is a classic source of bugs — a notification failure that rolls
back a legitimate transfer, or a queue retry that credits an account twice.
Keeping them apart is why WhatsApp being down cannot fail a transfer.

> The notification is derived from the already-persisted event flow, so it
> reflects a committed state change. The WebSocket itself only *delivers* that
> news; it does not *create* it.

## 10. Why exactly-once delivery cannot be assumed

"Exactly once" sounds achievable and is effectively not, end to end:

- Kafka delivers **at-least-once**. A consumer may crash after handling a
  message but before committing its offset, so it is redelivered.
- A WebSocket has no acknowledgement-by-default; a socket that dies mid-send
  gives no reliable "you got it" signal.
- WhatsApp providers retry, queue, and rate-limit on their own schedule, and
  they can accept a message and still fail to deliver it.

True exactly-once would require idempotent consumers, deduplication, and
provider-side idempotency keys across a network boundary nobody controls.

So PyBank is honest: **at-least-once, best-effort, idempotent where cheap.**
Duplicate notifications are tolerated and keyed by `event_id`; duplicates never
touch financial state. Claiming otherwise would be a lie the architecture
cannot keep.

## 11. Why user isolation matters

A global broadcast of banking events would be a serious data leak: every
connected user would see every other user's transfers.

Correct routing is:

```
event → account/customer → authorized user → socket
```

The server resolves ownership from the database. The client cannot request
someone else's data, because **the client sends no subscription at all** — it
only receives. Even a hostile message like `{"account_id": "someone-else"}` is
ignored, because nothing accepts it.

This was verified live, not just asserted: during a transfer between Alice and
Bob, a third connected customer (Carol) received **nothing**.

## 12. Why distributed WebSocket infrastructure is deferred

PyBank's connection manager is **process-local**: sockets live in one process's
memory. That is fine for one replica and honest to document as a limitation.

Scaling to several replicas needs shared fan-out. If the Fraud service publishes
`risk.assessed` and replica 2's consumer picks it up, but Alice's socket is held
by replica 1, nothing is delivered unless the events are shared — via Redis
Pub/Sub, a Kafka topic per instance, or a dedicated gateway.

Building that properly (sticky routing, reconnect correctness, backpressure) is
real distributed-systems work with its own failure modes. Phase 15's purpose is
to understand *why* the mechanism is needed, so it is documented and deferred
rather than half-built.

## 13. A real-world example

Priya has the PyBank dashboard open on her laptop, and WhatsApp notifications on
her phone. She sends ₹2,500 to a friend.

1. She presses **Send**. The browser POSTs `/transfers` with her JWT.
2. Banking validates, updates both balances, and **commits to PostgreSQL**.
3. In the *same* transaction, an outbox row is written. The transfer is durable
   before anyone is told about it.
4. A relay publishes `transfer.completed` to Kafka and marks the row published.
5. The Fraud service consumes it, scores the transfer, and publishes
   `risk.assessed`.
6. The realtime consumer maps both events to notifications, resolving recipients
   from the database.
7. Priya's open WebSocket receives "Your transfer of ₹2,500 was sent." — her
   balance updates with no refresh.
8. If the risk were `HIGH`, she would also get a security alert.
9. If WhatsApp is configured, an SMS-style message reaches her phone. If it is
   down, she still gets the WebSocket notice and the transfer still succeeded.

Now the failure cases:

- Her laptop sleeps → the socket closes. The server releases it. Money moved
  anyway. On wake, the client reconnects with backoff.
- WhatsApp is down → the transfer succeeded; the failure is logged and counted.
  Nothing is silently reported as delivered.
- The fraud consumer is slow → her dashboard still updates. The notification
  arrives a moment later.
- A bystander is logged in → receives nothing, because they own no account in
  the transfer.
