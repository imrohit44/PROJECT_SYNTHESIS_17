# Learning Guide: Phase 5

## React

React describes UI as components that render from state and props. Components make pages composable without moving banking rules into the browser.

## TypeScript

TypeScript turns the backend API contract into compile-time types. It catches mismatched fields and states before the browser runs. Types describe data; they do not duplicate account rules.

## Axios

Axios is the single HTTP transport boundary. The client adds authorization headers, extracts safe backend errors, and retries one expired access-token request after refresh. `fetch` could do the same with more local plumbing.

## React Query

TanStack React Query manages server state, loading/error states, caching, and mutation invalidation. It is preferable to copying API responses into a large global store. Redux remains unnecessary until there is a genuine cross-cutting client-state problem.

## Tailwind and CSS

Tailwind is integrated through Vite, while the visual language is kept in one stylesheet with responsive layout rules and design tokens. This phase prioritizes usable workflows, readable hierarchy, focus states, and mobile layout over decorative complexity.

## Authentication in the browser

The UI stores tokens in `sessionStorage` for this learning phase. This is less persistent than `localStorage`, but it is not immune to XSS because JavaScript can read it. A hardened production implementation should move refresh handling to HttpOnly cookies and carefully address CSRF, CSP, key rotation, and token revocation.

## Protected routes and authorization

React Router redirects users without a session. It hides admin navigation for customers, but this is only UX. The FastAPI backend checks the token, role, and account ownership on every protected request.

## CORS and configuration

The browser treats different ports as different origins. FastAPI explicitly allows the configured Vite origin, and the frontend reads its API URL from `VITE_API_BASE_URL`. Wildcard origins are avoided when credentials or security assumptions are involved.

## Loading, errors, and empty states

Every API-driven screen has a loading state, a safe error state, and an empty state. Backend error envelopes are converted to user-facing messages without exposing SQL, stack traces, or JWT internals.

## Alternatives and future

- `fetch` instead of Axios for a smaller dependency surface.
- Redux/Zustand if complex client-only state emerges.
- Next.js or server-side rendering if SEO or server-rendered workflows matter.
- WebSockets for real-time notifications in a later phase.
- Native mobile clients can reuse the same versioned API.

The frontend is intentionally a client. Banking decisions stay in FastAPI, application services, the domain, and PostgreSQL.
