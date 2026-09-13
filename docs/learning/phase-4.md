# Learning Guide: Phase 4

## What authentication is

Authentication verifies identity. PyBank accepts an email and password, verifies the password against an Argon2id hash, and issues signed JWT tokens.

## Why PyBank needs it

Before Phase 4, anyone who knew an account ID could call banking endpoints. Authentication gives the application a reliable caller identity that authorization policies can use.

## User versus Customer

A User is a login identity. A Customer is a banking identity and account owner. Keeping them separate prevents login concerns from leaking into banking domain entities and leaves room for one identity system to support more than one business concept later.

## Password security

Passwords are never stored directly. Argon2id turns a password into a one-way, salted hash. Login verifies the supplied password against that hash. The application never logs or returns plaintext passwords or hashes.

A password hash is not encryption: it is intentionally difficult to reverse. A future deployment should also add password reset, breach monitoring, rotation policy, and secret management.

## JWT access and refresh tokens

An access token is short-lived and used on protected requests. A refresh token lasts longer and is exchanged for new tokens. Each token has an explicit `type` claim, so an access token cannot be submitted to the refresh endpoint.

JWT is used here because it is understandable and works well for a modular API. Alternatives include server-side sessions, OAuth/OIDC, or an external identity provider. JWT makes request validation stateless, but stateless refresh tokens are harder to revoke immediately.

## Authorization and RBAC

Authorization decides what an authenticated user may do. PyBank has `customer` and `admin` roles. The admin-only user listing demonstrates role-based access control. Ownership policies separately verify that a customer owns the account involved in a request.

## Account ownership

Account IDs are not authorization. Every account read, transaction read, deposit, withdrawal, and transfer source is checked against the authenticated user's customer ID. Knowing another account's UUID does not grant access.

## Rate limiting

Phase 4 uses a process-local login limiter. It is useful for a single development process but does not coordinate across multiple workers or servers. Phase 8 can replace the isolated limiter with Redis-backed distributed limiting.

## Security headers and events

Security middleware adds browser-hardening headers appropriate for an API. HSTS is omitted on local HTTP because it is a deployment/HTTPS decision. Local security events record successes, failures, rate limits, and ownership denials without sensitive material. Later phases can send those events to centralized monitoring.

## Configuration and secrets

JWT secret, token lifetimes, password policy, and rate limits come from environment-backed typed settings. `.env` is ignored by Git. The example file contains placeholders only. A production deployment should use a secret manager and rotate signing keys.

## Testing strategy

Authentication tests verify hashing, generic failures, inactive users, token types, refresh behavior, RBAC, and rate limiting. API tests verify HTTP contracts and ownership. Domain tests remain database and authentication independent.

## Limitations

Refresh tokens are stateless and cannot be individually revoked. Rate limiting is process-local. There is no MFA, password reset, key rotation, external identity provider, Redis, or centralized audit pipeline. This is a learning implementation of secure fundamentals, not a real banking security certification.
