# Phase 4 Architecture

## Authentication architecture

```text
Client
  |
  +--> POST /api/v1/auth/register
  +--> POST /api/v1/auth/login
  +--> POST /api/v1/auth/refresh
  |
  v
FastAPI authentication router
  |
  v
AuthApplicationService
  |
  +--> Argon2id password service
  +--> JWT token service
  +--> User/Customer persistence
  `--> PostgreSQL

Protected request
  |
  v
Bearer token dependency
  |
  v
Decode and validate JWT claims
  |
  v
Load active User
  |
  +--> role authorization
  `--> account ownership policy
          |
          v
      Banking application service
          |
          v
        Domain
```

## User versus Customer

`User` is the authentication identity: email, Argon2id password hash, role, and active status. `Customer` is the banking identity that owns accounts. They are separate concepts connected by a unique `users.customer_id` foreign key. Registration creates both in one database transaction.

The domain customer/account entities remain unaware of users, JWTs, and passwords. The User persistence model belongs to the infrastructure/authentication boundary.

## Tokens

Access tokens are short-lived and contain `sub`, `role`, `type=access`, `iat`, and `exp`. Refresh tokens have a longer lifetime and contain `type=refresh`. The authentication dependency accepts only access tokens; the refresh endpoint accepts only refresh tokens. Refresh tokens are stateless in Phase 4 and are not persisted, which keeps the implementation small but prevents server-side revocation until a later token-store design.

## Authorization

Authentication answers who the caller is. Authorization is separate:

- `require_role(UserRole.ADMIN)` protects `GET /api/v1/users`.
- `authorize_customer` protects customer profile/account creation access.
- `authorize_account` checks account ownership before retrieval, transactions, deposits, withdrawals, and transfer source use.
- Administrators bypass customer ownership checks according to the explicit Phase 4 policy.

## Security controls

- Argon2id hashes passwords before persistence.
- Generic authentication failures avoid revealing whether an email exists.
- JWT secrets and lifetimes come from typed configuration.
- Login attempts use a process-local bounded window limiter.
- Security events log event names and safe identifiers, never passwords, hashes, tokens, or secrets.
- API responses add `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a restrictive Content Security Policy. HSTS is intentionally omitted for local HTTP.
- Database uniqueness and role constraints remain a second line of defense.

## Database change

Migration `0002_users` adds `users` without modifying existing tables. It enforces unique email, unique customer relationship, valid roles, non-null password hash, and active status. Alembic upgrade was verified against PostgreSQL 18.

## Future evolution

The process-local rate limiter can move to Redis when multiple application instances exist. Security events can later flow through Kafka into centralized audit monitoring. External identity providers, token revocation, key rotation, and stronger session controls belong to later hardening work.
