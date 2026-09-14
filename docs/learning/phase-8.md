# Phase 8 Learning - Redis

Redis is an in-memory data store. PyBank uses it for performance and shared
coordination, not as the banking ledger.

## Why Redis Exists

PostgreSQL is durable and authoritative. Redis is fast and temporary. It helps
with repeated reads and shared counters such as login rate limiting.

## Cache-Aside

PyBank uses cache-aside:

```text
request
  |
  +-- cache hit: return cached JSON representation
  |
  +-- cache miss: read PostgreSQL, store JSON in Redis with TTL, return
```

A hit means Redis already had the value. A miss means the app had to read from
PostgreSQL.

## TTL and Invalidation

TTL means time to live. Cached values expire automatically after a short period.
Invalidation deletes related keys after successful writes. TTL reduces stale
data; invalidation reduces it further. Neither creates strong consistency.

For banking correctness:

```text
PostgreSQL transaction > Redis cache
```

## Serialization

PyBank stores explicit JSON-compatible API representations in Redis. It does not
pickle domain objects. This keeps Decimal, enum, and datetime handling visible
and safer.

## Cache Keys

Keys identify data without secrets:

- `customer:{customer_id}`
- `account:{account_id}`
- `customer:{customer_id}:accounts`

Passwords, tokens, and sensitive request bodies do not belong in Redis keys or
values.

## Rate Limiting

A process-local limiter only protects one backend process. Redis-backed limiting
shares counters:

```text
Backend A \
Backend B --> Redis login counter
Backend C /
```

PyBank uses simple `INCR` plus `EXPIRE`. If Redis is down, the limiter fails
open so users are not locked out because a performance dependency failed. A
production system might choose differently.

## Docker Networking

Inside Compose, the backend connects to:

```text
redis://redis:6379/0
```

`localhost` inside a container means the same container, not another service.

## Performance Measurement

The benchmark script compares a cold account read with a warm account read. It
is useful for learning cache behavior, but local timings are noisy and do not
represent production capacity.

## What Redis Does Not Solve

Redis does not make incorrect code correct. It does not replace migrations,
authorization, durable storage, backups, or PostgreSQL transactions. Caching can
also make systems worse when stale data, invalidation bugs, or unnecessary
complexity outweigh the read-performance benefit.
