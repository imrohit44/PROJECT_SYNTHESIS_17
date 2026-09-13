# Phase 5 Architecture

## Frontend boundary

```text
React pages and components
  |
  v
Feature hooks and React Query
  |
  v
Central Axios client
  |
  v
FastAPI /api/v1
  |
  v
Authentication, application services, domain, PostgreSQL
```

The frontend is an untrusted client. It owns presentation, interaction, navigation, client-side form checks, and server-state caching. The backend remains authoritative for authentication, authorization, account ownership, balances, transactions, and all banking rules.

## Structure

- `src/app`: routing and authentication context.
- `src/components`: shared shell and small UI primitives.
- `src/pages`: route-level screens.
- `src/lib/api.ts`: one Axios client with bearer headers and one-shot refresh retry.
- `src/lib/queries.ts`: React Query account, detail, transaction, and mutation hooks.
- `src/types`: API response/request contracts copied from the backend schemas.

## Authentication and token strategy

This learning frontend stores access and refresh tokens in `sessionStorage`. It limits persistence across browser restarts and keeps the implementation understandable, but both tokens remain readable by JavaScript and therefore exposed if an XSS vulnerability exists. The frontend never displays or logs refresh tokens.

A hardened production banking client should prefer an architecture using an HttpOnly, Secure, SameSite refresh cookie, a short-lived in-memory access token, a strong Content Security Policy, and possibly a backend-for-frontend. Token storage alone does not solve XSS or CSRF risk.

Axios attaches the access token. A single shared refresh promise prevents concurrent requests from refreshing repeatedly. A failed refresh clears session state and protected routes redirect to login. Backend authorization remains authoritative even when the UI hides admin navigation.

## CORS and environment

The backend accepts the explicit `FRONTEND_ORIGIN` development origin. The frontend reads `VITE_API_BASE_URL`; URLs are not scattered through components. Production should provide an explicit deployed origin and HTTPS configuration.

## React Query strategy

Queries own server state and cache lifetimes. Mutations invalidate affected account and transaction keys after the backend confirms success. The frontend never derives an authoritative balance from transaction history.

## Known contract note

Phase 5 added `GET /api/v1/accounts` because the existing backend exposed only account-by-ID operations. It returns accounts already authorized by the backend for the authenticated customer.
