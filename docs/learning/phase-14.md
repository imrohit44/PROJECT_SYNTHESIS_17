# Phase 14 Learning — LLM Banking Assistant

## What we built

A read-only banking assistant: the user asks "What's my balance?" in plain
language, an LLM decides which tool to call, and the backend executes that
tool against the *authenticated* user's data through the same service layer
the REST API uses.

## Core lessons

### 1. The LLM proposes; the backend disposes

The single most important design rule. An LLM is a probabilistic text engine,
not an authority. It can *request* `get_recent_transactions(limit=10)`; it
cannot decide *whose* transactions. Identity comes from the JWT, is written
into a backend-owned `AgentContext`, and every tool re-scopes by
`customer_id`. Model-supplied arguments are untrusted input, full stop.

### 2. A prompt is not a security boundary

Telling the model "you are read-only" is good hygiene, not enforcement — a
sufficiently motivated prompt injection can always talk a model out of its
instructions. That is why:

- the tool registry is an **allowlist of four named functions** (unknown names
  raise before any code path resolves),
- arguments go through **strict Pydantic models** (`extra="forbid"`),
- and the tests use a *scripted hostile model*, not a cooperative one.

If the backend outcome is safe even when the model is hostile, the prompt
becomes a nice-to-have rather than the last line of defense.

### 3. There is no generic execution mechanism — on purpose

No `eval`, no dynamic `import`, no "run this SQL/Cypher", no HTTP tool that
accepts arbitrary URLs. Every such shortcut would convert a prompt-injection
bug into a breach. The four tools are narrow enough that adding one is a
deliberate, reviewable code change (the frozen-allowlist test enforces this).

### 4. Reuse the existing service layer

Tools call `BankApplicationService` and the Fraud service's existing HTTP API
instead of writing new queries. This automatically inherits every invariant
built in Phases 0–13: ownership checks, atomic transfers, idempotency, fraud
score semantics. The assistant cannot violate rules it never reimplements.

### 5. Bounded loops matter

LLMs can (and do) call tools repeatedly. `LLM_MAX_TOOL_CALLS=3` converts
"possible infinite tool loop" into a deterministic `AgentToolsExceededError`
→ HTTP 400. Bounding provider calls also bounds cost and latency.

### 6. Failure must be boring

Missing API key, provider timeout, malformed tool call, fraud service down —
all map to small, generic API errors (503/400) with metrics status labels.
Tests assert that responses never contain stack traces, provider URLs, or the
API key. An assistant that is optional must never take the bank down with it.

### 7. Observability without a second system

Phase 14 added two counters with strictly bounded labels (allowlisted tool
names only, unknown bucketed to `unknown`), one span (`assistant.chat`), and
structlog events — all riding the Phase 11 correlation/trace/metrics plumbing.
No `user_id`/`transaction_id` labels: Prometheus labels must stay low-cardinality,
and IDs in labels would be both an operational and a privacy problem.

### 8. Provider abstraction early, vendor lock-in never

`LLMClient` is a thin OpenAI-compatible chat-completions client over `httpx`.
The rest of the app depends only on `generate_with_tools()`. Swapping providers
means changing base URL/model/key — not touching the agent, tools, or API.

### 9. A demo should not dead-end on credentials

Without an API key the assistant used to answer `503 "The banking assistant is
not configured"`, even though every read-only tool was available. The fix was not
a second AI system: it was a **deterministic assistant behind the same seam**.

```text
LLM_API_KEY set  -> existing provider -> existing tools
LLM_API_KEY unset -> deterministic fallback -> the same tools
```

The fallback exposes `generate_with_tools()` and a `model` attribute, so the
agent loop, the registry, and the JWT-derived `AgentContext` are literally the
same code. It recognises a handful of intents, calls the same tools, and renders
only what those tools returned — no model, no provider, no new dependency, no
container. Anything it does not recognise returns the list of supported
questions instead of a guess.

The lesson: the same seam that made the provider swappable also made "answer
without a provider" a small, safe change. Design the interface around the
*decision* you want to be able to make later.

## Frontend note (the Vitest "unhandled rejection" mystery

The assistant page's test initially failed intermittently with what looked
like an unhandled `AxiosError`. Root cause was a Vitest footgun, not the
component: `beforeEach(() => vi.mocked(fn).mockReset())` — an *expression-bodied*
hook — returns the mock (because `mockReset()` returns `stub`), and the Vitest
runner registers any function return value as a per-test cleanup, invoking the
mock *again* after the test with whatever implementation was last set. The
cleanup awaited a rejected promise and failed the test with it. Fix: braced
hook bodies (`beforeEach(() => { ...mockReset(); })`) so hooks return
`undefined`. Lesson: in Vitest, hook return values are meaningful — keep hook
bodies braced whenever the last expression could be a function.

## Verification approach

- Deterministic, free, CI-safe: a scripted `_ScriptedLLM` double produces
  exact tool calls (including hostile ones) — no paid API needed.
- Security tests build two customers and assert Bob's IDs never appear in
  Alice's observations, even when the "model" asks for everything.
- Endpoint tests cover 401, 422, 429, 503 (provider error), fallback mode, tool-error
  surfacing, and rate limiting before the model runs.
- Frontend: React Testing Library + mocked `sendAssistantMessage`.

## What we deliberately did not build

Conversation memory, streaming, write tools, RAG over documents, fine-tuning —
each would expand the attack surface or scope without solving the phase's
actual problem: safe, authorized, read-only answers grounded in real backend
data.
