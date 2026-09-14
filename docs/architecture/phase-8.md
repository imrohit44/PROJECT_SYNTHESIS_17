# Phase 8 Architecture - Redis Performance Layer

Redis is added as a performance and coordination dependency. PostgreSQL remains
the source of truth for balances, accounts, customers, transactions, and all
durable banking state.

```text
Browser
  |
  v
Frontend
  |
  v
FastAPI backend
  |        |
  |        +--> Redis cache and login rate-limit counters
  |
  +----------> PostgreSQL source of truth
```

## Compose Networking

The backend reaches Redis with:

```text
redis://redis:6379/0
```

`redis` is the Compose service name. `localhost` inside the backend container
would mean the backend container itself, not the Redis container.

Redis stays on the private Compose network and is not published to the host by
default.

## Cache Architecture

The domain layer does not import Redis. API/application adapters depend on a
small cache abstraction:

```text
get_json
set_json with TTL
delete
```

The Redis implementation stores JSON representations, not pickled domain
objects.

## Cached Resources

- Customer profile: `customer:{customer_id}`, TTL 300 seconds.
- Account details: `account:{account_id}`, TTL 60 seconds.
- Customer account list: `customer:{customer_id}:accounts`, TTL 60 seconds.

Transactions and financial mutations are not cached as authoritative data.

## Cache-Aside Flow

```text
read request
  |
  +--> Redis hit: return cached representation
  |
  +--> Redis miss: read PostgreSQL, serialize DTO, store in Redis, return
```

## Invalidation

Invalidation happens only after successful database operations:

- Create account: delete the customer account-list cache.
- Deposit/withdrawal: delete account detail and owner account-list caches.
- Transfer: delete both account detail caches and both owner account-list caches.
- Customer creation: delete that customer profile key.

Failed financial operations do not invalidate cache state.

## Failure Behavior

Redis failures are logged and treated as cache misses. Reads fall back to
PostgreSQL. Banking writes still commit through PostgreSQL even if cache
invalidation fails.

Login rate limiting uses Redis when configured. If Redis is unavailable, this
educational stack fails open for availability and documents the tradeoff.

## Performance Measurement

Use:

```powershell
.\docker\cache-benchmark.ps1
```

It performs one cold account read and one warm account read. These local numbers
show behavior, not production throughput.
