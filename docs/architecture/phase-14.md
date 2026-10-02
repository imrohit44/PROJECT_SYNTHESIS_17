# Phase 14 — LLM Banking Assistant (Read-Only Agent)

## Overview

Phase 14 adds an authenticated, **read-only** banking assistant. An LLM
chooses which *information* to fetch through tool calling; the backend decides
*what is allowed*. The model never touches PostgreSQL, Redis, Kafka, or Neo4j
directly, never supplies identity, and cannot perform any banking mutation.

```
                         User
                          │
                          ▼
                   React Frontend
                          │  POST /api/v1/assistant/chat (JWT)
                          ▼
                   Assistant API
                          │  builds AgentContext from the JWT principal
                          ▼
                     LLM Agent  ◄──── provider-neutral LLMClient
                          │            (OpenAI-compatible chat completions)
                          ▼
                   Tool Registry  ── allowlist-only, Pydantic-validated
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
      Account Tool   Transaction Tool   Fraud Tool
          │               │               │
          └───────────────┼───────────────┘
                          ▼
              BankApplicationService / Fraud HTTP API
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
          PostgreSQL             Fraud Service
                                      │
                                  ML + Neo4j
```

**The LLM is not the banking authority. The backend remains authoritative.**

## Component map

| Component | Location |
|---|---|
| Assistant endpoint | `backend/app/api/v1/assistant.py` |
| Agent loop | `backend/app/assistant/agent.py` |
| Tool registry | `backend/app/assistant/registry.py` |
| Read-only tools | `backend/app/assistant/tools.py` |
| Tool argument schemas | `backend/app/assistant/schemas.py` |
| System prompt (v1) | `backend/app/assistant/prompts.py` |
| Assistant metrics | `backend/app/assistant/metrics.py` |
| LLM client abstraction | `backend/app/llm/client.py` |
| LLM transport models | `backend/app/llm/models.py` |
| Lightweight fallback assistant | `backend/app/assistant/fallback.py` |
| Settings | `backend/app/core/config.py` (`LLM_*`, `ASSISTANT_*`) |
| Frontend page | `frontend/src/pages/Assistant.tsx` |
| Frontend API call | `frontend/src/lib/api.ts` (`sendAssistantMessage`) |
| Security tests | `backend/tests/assistant/test_security.py` |

## Why the LLM does not access databases directly

1. **No generic execution surface.** If the model could emit SQL, Cypher, or
   code, every prompt-injection technique becomes a data-breach technique. The
   registry exposes exactly four named functions; anything else raises
   `ToolRegistryError` before any code runs.
2. **Authorization must be deterministic.** Row scoping depends on the JWT
   principal (`user_id`, `customer_id`, `role`). Tool arguments are untrusted
   input; identity is injected server-side into `AgentContext`.
3. **The banking domain already has an API.** Tools reuse
   `BankApplicationService` — the same service layer the REST API uses — so the
   assistant can never bypass invariants (balances, ownership, status) that the
   ledger enforces.
4. **Read-only by construction.** Only four read tools exist. A model that
   asks for `transfer` or `run_sql` gets a rejection record, not an action.

## Tool registry (the capability boundary)

`ToolRegistry` is an explicit allowlist. Frozen tool set:

| Tool | Arguments | Backend behavior |
|---|---|---|
| `get_account_summary` | none (strict) | Own accounts via `BankApplicationService` |
| `get_recent_transactions` | `limit` 1–50 (default 10), optional `account_id` | Own accounts only, sorted, hard-capped |
| `get_transaction_details` | `transaction_id` (1–64 chars) | Found only if the transaction belongs to the caller |
| `get_fraud_assessment` | `transaction_id` (1–64 chars) | Ownership check first, then Fraud service HTTP API with a response-field allowlist |

Rules enforced by the registry itself:

- **Unknown tool name → `ToolRegistryError`.** No dynamic import, no `getattr`
  on modules, no reflection. `drop_database`, `execute_cypher`, `__import__`,
  `graph_query` are all rejected identically.
- **Arguments must be a JSON object**, then validated by the tool's Pydantic
  model with `extra="forbid"` — a model cannot smuggle `customer_id`, `user_id`,
  or `role` into a tool call.
- **Hard maximums live in the schema** (`MAX_TRANSACTION_LIMIT = 50`,
  `ge=1, le=50`), so `limit=100000` or `limit=-1` raises `ValidationError`
  before any query runs.
- Tool results are serialized to compact JSON observations for the model;
  failures become `{"error": ...}` observations with sanitized messages.

## Identity and trust boundary

- The endpoint depends on `get_current_user` (JWT). No token → `401
  AUTHENTICATION_REQUIRED`.
- `AgentContext` is constructed **only** from the authenticated principal and
  backend services; the LLM can never populate it.
- Each tool re-scopes by `context.user.customer_id`. Admin role is honored by
  `_assert_account_access`, mirroring existing REST authorization.
- Cross-user reads (even with a known foreign `transaction_id`) return
  `{"found": false}` or an ownership error — verified by
  `TestCrossUserIsolation`.

## Agent orchestration and loop safety

- `AgentService.run()` = system prompt + user message → provider call →
  optional tool rounds → final answer.
- Hard ceiling: `LLM_MAX_TOOL_CALLS` (default **3**) tool rounds per request.
  A model that never stops raises `AgentToolsExceededError` → HTTP `400` with
  a generic detail. No infinite loop, no runaway provider spend.
- Malformed/failed tool calls become error observations; the agent continues
  or degrades gracefully — it never raises provider internals to the client.

## Provider configuration

| Setting | Env var | Default |
|---|---|---|
| Provider flag | `LLM_PROVIDER` | empty (assistant disabled) |
| API key | `LLM_API_KEY` | empty |
| Model | `LLM_MODEL` | provider default |
| Base URL | `LLM_BASE_URL` | OpenAI-compatible `/v1` |
| Timeout | `LLM_TIMEOUT_SECONDS` | bounded |
| Max output tokens | `LLM_MAX_OUTPUT_TOKENS` | 512 |
| Max tool rounds | `LLM_MAX_TOOL_CALLS` | 3 |
| Input cap | `ASSISTANT_MAX_INPUT_CHARS` | 2000 |
| Rate limit | `ASSISTANT_RATE_LIMIT` / `_WINDOW_SECONDS` | 10 / 60s per user |

`LLMClient` speaks the OpenAI-compatible chat-completions protocol with native
tool calling over `httpx` — provider SDKs and credentials never leak past this
class.

## Assistant modes

The assistant answers in one of two modes, chosen by provider configuration only:

| Mode | When | What answers |
|---|---|---|
| `llm` | `LLM_API_KEY` and `LLM_MODEL` are set | The Phase 14 agent loop calling the configured provider, unchanged |
| `fallback` | No provider is configured | A deterministic assistant that plans read-only tool calls in ordinary Python |

`backend/app/assistant/fallback.py` implements the fallback behind the same seam
as the provider: it exposes `generate_with_tools(...)` and a `model` attribute,
so `AgentService`, `ToolRegistry`, and the JWT-derived `AgentContext` are reused
exactly as they are for the LLM. Nothing in the Phase 14 loop changes.

The fallback recognises a small intent set — account summary, recent
transactions, account details, risk/fraud status, and help — and answers from
tool observations only. It never invents a value, never calls anything outside
the frozen read-only allowlist, and cannot turn an account or transaction id
from the user's message into access: the risk path takes its id from the
transactions tool's own observation. Anything it does not recognise returns the
list of supported questions instead of a guess.

This exists so the banking application stays demonstrable without external AI
credentials. It adds no model, provider, framework, container, or dependency.
`GET /api/v1/assistant/status` reports `{"available": true, "mode": ...}` — and
nothing else, so no provider name, endpoint, or credential reaches the client.

## Error mapping (no stack traces, no secrets)

| Condition | HTTP | Metric status |
|---|---|---|
| Missing/invalid JWT | 401 | (rejected by auth) |
| Oversized message | 422 | `rejected` |
| Rate limited | 429 | `rejected` |
| No provider configured | 200 (fallback answers) | `success` |
| Provider error/timeout/malformed response | 503 | `llm_error` |
| Tool-round limit exceeded | 400 | `rejected` |
| Unknown tool / invalid args / tool failure | 200 with error observation | `assistant_tool_calls_total{status="error"}` |

A tool failure inside the fallback becomes a plain "I couldn't retrieve your
account information right now" reply — never a stack trace, path, or provider
detail.

Responses are asserted in tests to never contain `api_key`, provider URLs,
`Traceback`, `ConnectError`, or the raw `LLM_API_KEY` value (which never has a
default).

## Read-only boundary

The system prompt (`banking-agent-v1`) tells the model it is read-only, but
**the prompt is guidance, not a control**. The real boundary:

- No write tool exists in the registry (asserted by
  `test_no_write_tools_registered`).
- The assistant cannot call REST mutation endpoints; tools only invoke read
  paths of `BankApplicationService` and a GET against the Fraud service.
- "Transfer ₹10,000", "Change my password", etc. can only produce a text
  refusal — zero banking mutation is possible through this path.

## Prompt injection posture

Injection attempts ("ignore your instructions", "show me every customer's
transactions", "call an admin tool", "execute SQL/Cypher") are covered by
deterministic tests (`test_model_prompt_injection_cannot_change_tool_authorization`)
that verify the *backend outcome*: results remain scoped to the caller's
`customer_id`, unknown tools are rejected, and no other customer's identifiers
appear in observations. Safety does not depend on the model refusing.

## Frontend

- `Assistant.tsx`: chat thread (`role="log"`), question field, loading state
  ("Thinking…"), per-tool-call chips (`tool · status`), error banner via
  `apiMessage` (shows the backend envelope message such as "The banking
  assistant is not configured", never internals). Explicit "Read-only" badge
  and hint: "The assistant can read your data. It can never move money."
- `sendAssistantMessage` posts to `/assistant/chat` through the existing axios
  instance (JWT header + refresh interceptor — no second auth path).
- Routing/nav entry added in `App.tsx` / `AppShell.tsx`, protected by the
  existing `ProtectedRoute`.
- Tests: `frontend/src/pages/Assistant.test.tsx` (5 tests) covering initial
  state, success flow with tool chips, tool-error rendering, backend error
  message surfacing, and the empty-question guard.

## Observability (Phase 11 stack, no second system)

- **Metrics** (`backend/app/assistant/metrics.py`), labels bounded:
  - `assistant_chats_total{status}` — `success | rejected | llm_error | not_configured`
  - `assistant_tool_calls_total{tool,status}` — tool names outside the
    allowlist are bucketed to `unknown`; **never** `user_id`, `customer_id`,
    `transaction_id`, or `conversation_id`.
- **Logs**: structlog events (`assistant_chat_completed`,
  `assistant_tool_rejected`, `assistant_tool_invalid_arguments`,
  `assistant_tool_failed`, `assistant_tool_limit_exceeded`) with bounded fields
  (`tool_calls`, `rounds`, `model`, `prompt_version`, `tool`). The Phase 11
  middleware/processor injects `correlation_id` automatically — no new
  correlation system was created.
- **Tracing**: one OTel span `assistant.chat` with attribute
  `pybank.assistant.tool_calls`. No user content, tokens, or message text in
  span attributes.

## Security summary

| Control | Mechanism |
|---|---|
| Authentication | JWT (`get_current_user`), 401 otherwise |
| Authorization | Per-tool re-scoping by JWT `customer_id`, admin honored |
| Cross-user protection | Ownership checks; foreign IDs return not-found |
| Read-only | 4-tool allowlist; no mutation path exists |
| Argument validation | Pydantic strict (`extra="forbid"`), hard max 50 |
| Identity spoofing | `AgentContext` built server-side; extra fields rejected |
| Loop safety | `LLM_MAX_TOOL_CALLS=3` → `AgentToolsExceededError` |
| Abuse | Per-user rate limit (10/min default), input length cap |
| Secrets | `LLM_API_KEY` env-only, empty default, never logged/echoed |

## Explicitly out of scope

Persistent conversation memory, streaming responses, write tools, RAG over
documents, fine-tuning, and voice/mobile surfaces belong to future phases —
not Phase 14.
