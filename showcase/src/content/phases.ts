/**
 * The seventeen phases of Project Synthesis 17, in the order they were built.
 *
 * Every fact here comes from `docs/architecture/phase-N.md` in the banking
 * repository. Nothing is invented: if a phase did not ship something, this
 * file says so — including in `tradeoff`, which names the cost the phase
 * accepted instead of hiding it.
 */
import type { Phase } from "./types";

export const phases: Phase[] = [
  {
    number: 0,
    id: "foundation",
    title: "A skeleton with a spine",
    track: "foundation",
    tagline: "FastAPI, one versioned router, one health endpoint — and a deliberate refusal to add anything else.",
    problem:
      "Nothing existed yet, so the real risk was starting wrong: framework code spreading everywhere before the shape of the system was decided.",
    change:
      "An entrypoint that only wires, a versioned /api/v1 router that owns route registration, one liveness endpoint, and settings and logging confined to core/.",
    result:
      "A spine every later phase plugs into without rewiring — and a standing precedent that adding anything has to argue for itself.",
    tradeoff:
      "Deliberately no database, cache, broker or containers. /health proves the process answers HTTP; readiness waits until there is a dependency worth checking.",
    stack: ["Python 3.12", "FastAPI", "Uvicorn", "pytest"],
    docPath: "docs/architecture/phase-0.md",
  },
  {
    number: 1,
    id: "domain-model",
    title: "Money rules before databases",
    track: "foundation",
    tagline: "The domain knows what a valid transfer is; nothing else does.",
    problem: "Transfer rules had nowhere to live except wherever the code happened to be written.",
    change:
      "A framework-free domain package — Account types, Transaction, Bank, TransferService — holding every money invariant the project will ever need.",
    result:
      "Decimal money with ROUND_HALF_EVEN, floats rejected for money, a failed transfer that changes neither balance nor history, all exercisable from a plain script before any storage exists.",
    tradeoff: "State lives in memory only; the phase ships no persistence and says so out loud.",
    stack: ["Python 3.12", "dataclasses", "Decimal", "ROUND_HALF_EVEN"],
    docPath: "docs/architecture/phase-1.md",
  },
  {
    number: 2,
    id: "api-boundary",
    title: "The API boundary",
    track: "foundation",
    tagline: "Routes translate HTTP into domain calls. They do not decide whether a transfer is valid.",
    problem: "HTTP handlers drift into deciding business rules unless the boundary between the two is explicit.",
    change:
      "Pydantic request and response schemas kept separate from domain entities, money serialized as two-decimal strings, and one error envelope mapping domain failures to stable codes.",
    result:
      "The external HTTP format can evolve without touching the objects that enforce the rules, and domain exceptions never learn about HTTP.",
    tradeoff:
      "State is still process-local — restarting Uvicorn erases the data, which the documentation states instead of pretending otherwise.",
    stack: ["Pydantic", "FastAPI routers", "httpx", "pytest"],
    docPath: "docs/architecture/phase-2.md",
  },

  {
    number: 3,
    id: "persistence",
    title: "Persistence without leaking the ORM",
    track: "foundation",
    tagline: "SQLAlchemy and Alembic arrive; the domain still imports neither.",
    problem: "Balances had to survive restarts without the ORM reaching into the domain or the API.",
    change:
      "SQLAlchemy models, mappers and Alembic live under infrastructure; a BankApplicationService orchestrates domain objects and one session, and transfers lock both accounts with SELECT ... FOR UPDATE in sorted id order.",
    result:
      "One commit updates both balances and inserts both records; foreign keys and balance constraints guard the schema as a second line of defence; the domain still imports neither SQLAlchemy nor Alembic.",
    tradeoff:
      "A mapper per type is bookkeeping the domain would not need — paid willingly so the framework-free core stays framework-free.",
    stack: ["SQLAlchemy 2", "PostgreSQL 18", "Alembic", "NUMERIC(18,2)"],
    docPath: "docs/architecture/phase-3.md",
  },
  {
    number: 4,
    id: "authentication",
    title: "Identity, modelled separately",
    track: "foundation",
    tagline: "A User authenticates. A Customer owns money. They are not the same row.",
    problem: "One row for login and money means authentication ends up owning balances.",
    change:
      "Registration creates a User and a Customer in one database transaction, linked by a unique foreign key; Argon2id hashes passwords and JWTs carry role and token type.",
    result:
      "The bearer dependency accepts only 15-minute access tokens and the refresh endpoint only 7-day refresh tokens; require_role, authorize_customer and authorize_account gate each resource instead of trusting the UI.",
    tradeoff:
      "Refresh tokens are stateless here, so revocation waits for a token store — recorded as a known limit, not glossed over.",
    stack: ["Argon2id", "JWT (HS256)", "Migration 0002_users", "Security headers"],
    docPath: "docs/architecture/phase-4.md",
  },
  {
    number: 5,
    id: "frontend",
    title: "A frontend that trusts nothing",
    track: "foundation",
    tagline: "The browser owns presentation. The backend stays authoritative about money.",
    problem: "A browser that trusts its own arithmetic turns rounding errors into money errors.",
    change:
      "A React and React Query SPA that renders server state and never computes balances; the token pair lives in sessionStorage, with the hardened production alternative documented.",
    result:
      "Registration through transfer works end to end, and GET /api/v1/accounts was added because the contract genuinely lacked it — the frontend drove the API, not the other way around.",
    tradeoff:
      "sessionStorage is readable by JavaScript; the HttpOnly-cookie design is documented rather than implemented in this phase.",
    stack: ["React", "React Query", "Axios", "Vite", "Vitest"],
    docPath: "docs/architecture/phase-5.md",
  },
  {
    number: 6,
    id: "quality-gates",
    title: "A feedback system, not a test count",
    track: "foundation",
    tagline: "Fast unit tests, honest integration tests, and an E2E gate marked NOT VERIFIED until it exists.",
    problem: "Without gates, every later phase spends its change budget re-checking the older ones.",
    change:
      "Tests organised by what they prove — domain invariants, security regressions, API contracts, persistence, PostgreSQL-specific locking — behind pytest, coverage, ruff and mypy.",
    result:
      "Fast SQLite-backed API feedback plus honest integration against real PostgreSQL, and Playwright documented as NOT VERIFIED until the Docker phase makes it possible.",
    tradeoff:
      "Coverage thresholds stay deliberately modest, because coverage is a signal rather than proof.",
    stack: ["pytest", "coverage.py", "ruff", "mypy", "Vitest"],
    docPath: "docs/architecture/phase-6.md",
  },
  {
    number: 7,
    id: "docker-compose",
    title: "Three containers, one private network",
    track: "platform",
    tagline: "PostgreSQL, the API and the built frontend, each in its own container and none of them guessing a hostname.",
    problem:
      "A stack that only runs on one laptop cannot be reviewed, and the PostgreSQL claims from the quality phase needed a reproducible environment.",
    change:
      "Three containers — PostgreSQL 18, the API, Nginx serving the built frontend — on one private pybank bridge network, with health-checked depends_on and the backend addressed as postgres:5432, never localhost.",
    result:
      "pg_isready and /api/v1/health gate the dependents, alembic runs at startup by RUN_MIGRATIONS flag, and smoke-test.ps1 walks register through transfer and history through the published ports.",
    tradeoff:
      "Host ports stay published and the environment is a development one — hardening is Phase 16's job, not this one's.",
    stack: ["Docker", "Docker Compose", "Nginx", "PostgreSQL 18 volume"],
    docPath: "docs/architecture/phase-7.md",
  },
  {
    number: 8,
    id: "redis-cache",
    title: "A cache that PostgreSQL outranks",
    track: "platform",
    tagline: "Redis makes reads fast. It never becomes the source of truth for money.",
    problem: "Every dashboard re-read the same profile and account rows from PostgreSQL on every visit.",
    change:
      "Cache-aside Redis with explicit TTLs — customer:{id} at 300 seconds, account:{id} and the owner list at 60 — behind a small abstraction, with invalidation only after a commit succeeds.",
    result:
      "Hot reads are served without touching the ledger, and a Redis outage degrades to a logged cache miss — never to a wrong answer about money.",
    tradeoff:
      "The cache can briefly disagree with PostgreSQL. Acceptable for reads, forbidden for money: transactions are never cached as authoritative data.",
    stack: ["Redis 7", "cache-aside", "JSON values", "TTL policy"],
    docPath: "docs/architecture/phase-8.md",
  },
  {
    number: 9,
    id: "event-backbone",
    title: "Kafka behind a transactional outbox",
    track: "platform",
    tagline: "The banking transaction and its event are written together, so no committed transfer goes unannounced.",
    problem: "A transfer that is committed but never announced leaves every other system guessing.",
    change:
      "Balances, transactions and an outbox row commit in one PostgreSQL transaction; a background publisher moves outbox rows to the single topic pybank.events, keyed by aggregate_id.",
    result:
      "No committed transfer goes unannounced; typed envelopes carry event_id and schema_version, and the audit consumer group records processed event ids so duplicates are ignored.",
    tradeoff:
      "At-least-once means duplicates reach consumers — paid for with idempotency — and order across partitions is explicitly not promised.",
    stack: ["Apache Kafka 3.9 (KRaft)", "transactional outbox", "processed_events", "consumer groups"],
    docPath: "docs/architecture/phase-9.md",
  },
  {
    number: 10,
    id: "fraud-service",
    title: "The first real service boundary",
    track: "intelligence",
    tagline: "The fraud domain gets its own service, its own database, and no shared Python code.",
    problem: "Fraud logic inside the banking API means scoring a transfer blocks the transfer.",
    change:
      "A second FastAPI service owning the pybank_fraud database, consuming transfer.completed and publishing risk.assessed — Kafka is the only channel between the two.",
    result:
      "Scoring happens after the money commits; cross-service database queries are prohibited, and running two replicas demonstrates the scaling limit: one sits idle on a single-partition topic.",
    tradeoff:
      "Network hops, serialization, eventual consistency and extra deployment surface — listed as costs in the docs, not hidden.",
    stack: ["FastAPI (fraud service)", "PostgreSQL pybank_fraud", "Kafka consumer groups"],
    docPath: "docs/architecture/phase-10.md",
  },
  {
    number: 11,
    id: "observability",
    title: "Seeing the system work",
    track: "intelligence",
    tagline: "Liveness says the process is up. Readiness says it can serve. Metrics and traces say what happened.",
    problem: "An async system is undebuggable when the request path ends at a commit and continues in a consumer.",
    change:
      "Liveness and readiness split apart; Prometheus, Grafana and Jaeger arrive; correlation_id and traceparent are stored on every outbox row and carried as Kafka headers.",
    result:
      "/ready checks PostgreSQL, Redis and Kafka with bounded timeouts; OpenTelemetry spans continue across the Kafka hand-off instead of pretending it is one continuous request.",
    tradeoff:
      "Trace context across the async hop is continued, not magically continuous — and readiness adds dependency probes to the hot loop of orchestration.",
    stack: ["Prometheus", "Grafana", "Jaeger", "OpenTelemetry"],
    docPath: "docs/architecture/phase-11.md",
  },
  {
    number: 12,
    id: "ml-fraud-model",
    title: "A learned signal beside the rules",
    track: "intelligence",
    tagline: "Rules stay the floor. A trained model may raise or lower a score, but it cannot silently skip a rule.",
    problem: "Rules alone miss patterns that only a trained signal can see.",
    change:
      "A GradientBoosting pipeline (fraud-model-v1) with threshold 0.86 chosen on the validation set; combined_score = 0.6 × rule_score + 0.4 × ml_probability; one features.py contract shared by trainer and consumer.",
    result:
      "A learned signal with train/serve skew removed as a class of bug, and loud failure instead of silent degradation: a missing artifact stops the service at startup.",
    tradeoff:
      "The model may move a score but never skip a rule — rules remain the floor, and a prediction failure fails the assessment rather than pretending ML ran.",
    stack: ["scikit-learn GradientBoosting", "StandardScaler pipeline", "joblib artifact"],
    docPath: "docs/architecture/phase-12.md",
  },
  {
    number: 13,
    id: "graph-risk",
    title: "Relationships as a read model",
    track: "intelligence",
    tagline: "Neo4j is rebuilt from events. It is never the ledger, and it can only add a bounded bonus.",
    problem: "One event cannot answer who else pays this beneficiary, or where that money goes next.",
    change:
      "Neo4j projected from pybank.events with three deterministic signals capped at 1.0, entering scoring only as graph_adjustment = min(0.15, 0.25 × graph_score).",
    result:
      "Relationship evidence enters the score bounded; the graph is derived, disposable, and can be dropped and rebuilt from events without touching a balance.",
    tradeoff:
      "Another datastore to project and keep fresh — bounded on purpose so a Neo4j outage contributes a neutral 0.0 and the assessment still completes.",
    stack: ["Neo4j 5", "Cypher projections", "fraud-graph-v1", "bounded adjustment"],
    docPath: "docs/architecture/phase-13.md",
  },
  {
    number: 14,
    id: "llm-assistant",
    title: "An assistant that can only read",
    track: "intelligence",
    tagline: "The model chooses what to look up. The backend decides what is allowed.",
    problem: "An LLM with real credentials against a banking API is a liability unless the limits are architectural.",
    change:
      "A read-only agent over an allowlisted tool registry; identity comes from the JWT principal, tool arguments are validated with Pydantic, and the LLM client is provider-neutral.",
    result:
      "The assistant answers questions about accounts, transactions and assessments; no prompt can claim another identity, and no mutation is possible from any prompt.",
    tradeoff:
      "Answers are only as good as the deliberately narrow read-only tool surface — the vendor is a configuration choice, the boundary is not.",
    stack: ["Tool calling", "Pydantic tool schemas", "Provider-neutral LLM client"],
    docPath: "docs/architecture/phase-14.md",
  },
  {
    number: 15,
    id: "realtime",
    title: "Kafka talks to services, WebSockets talk to people",
    track: "intelligence",
    tagline: "One new consumer, no new service, no new database — and the customer sees risk the moment it is assessed.",
    problem: "Without this phase, a customer learns about a risk assessment by refreshing the page.",
    change:
      "A third consumer group, pybank-realtime-consumer, routes transfer.completed and risk.assessed into channels; POST /ws/ticket issues short-lived tickets so the socket never carries a long-lived credential.",
    result:
      "risk.assessed reaches the browser over the WebSocket it already holds, and WhatsApp carries the message to someone not looking at the app — the loop opened at Phase 9 closes visibly.",
    tradeoff:
      "Three delivery channels, none of them authoritative: a missed push changes no state, because state was never in the push.",
    stack: ["FastAPI WebSockets", "WebSocketManager", "Notification routing"],
    docPath: "docs/architecture/phase-15.md",
  },
  {
    number: 16,
    id: "cicd-cloud",
    title: "From a laptop to a public URL",
    track: "delivery",
    tagline: "Three gates, immutable image tags, one host, and a rollback that was actually documented.",
    problem: "A stack that only runs on a laptop proves nothing about running in public.",
    change:
      "GitHub Actions gated on workflow_run success, three images tagged with the validated commit SHA on GHCR, and the same Compose stack on a single AWS EC2 host behind Nginx over HTTPS.",
    result:
      "Deploy verifies /health, /ready and a smoke test before declaring success; rollback is a tag change, not a rebuild; the Phase 6 gates became CI steps unchanged.",
    tradeoff:
      "One host is honesty about scope: real gates and documented rollback, but no high availability — and the docs say exactly that.",
    stack: ["GitHub Actions", "GHCR", "AWS EC2", "Nginx over HTTPS"],
    docPath: "docs/architecture/phase-16.md",
  },
];
