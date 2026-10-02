# Learning Guide: Phase 0

## 1. What is software architecture?

Software architecture is the set of important decisions about system boundaries, responsibilities, dependencies, and how parts communicate. It is not a complicated diagram for its own sake. It gives future code a stable place to live and makes change easier to reason about.

## 2. Why project structure matters

Folders and modules communicate ownership. In Project Synthesis 17, API routes, configuration, logging, and tests have separate homes. This prevents one file from becoming the place where every concern is mixed together. A structure is useful when it helps a new developer predict where a change belongs.

## 3. Why configuration is separate from code

Application code describes behavior; configuration describes how that behavior runs in an environment. Keeping them separate means development, testing, and production can use different values without editing Python files or rebuilding the application.

## 4. What environment variables are

Environment variables are named values supplied by the operating system or process runner. Pydantic Settings reads values such as `APP_ENV` and `LOG_LEVEL`, converts them to the declared Python types, and validates them when the application starts.

## 5. Why secrets should not be committed

Git history is durable and easy to copy. A password or token committed once may remain accessible even after deletion. `.env` is ignored, while `.env.example` documents safe names and sample values without containing credentials. Production secrets will later come from a deployment secret manager.

## 6. What FastAPI provides

FastAPI maps HTTP requests to Python functions, validates request and response data, generates OpenAPI documentation, and supports asynchronous handlers. Phase 0 uses only its application and routing features.

## 7. What ASGI is

ASGI is a Python standard interface between asynchronous-capable web applications and servers. It supports HTTP and other connection types. FastAPI is an ASGI application, which is why an ASGI server such as Uvicorn can run it.

## 8. Why Uvicorn is used

Uvicorn is a lightweight ASGI server. It accepts network connections, passes requests to FastAPI, and returns responses. It is a good local development server and a common building block for production deployments.

## 9. What API versioning means

The `/api/v1` prefix identifies the first public contract. If a future breaking change is required, `/api/v2` can be introduced while clients migrate from version 1. Versioning does not make bad API design harmless, but it makes intentional evolution possible.

## 10. What health checks are

A liveness check answers, "Is the process alive?" The Phase 0 endpoint returns `{"status": "ok"}`. Readiness answers, "Can the process safely serve traffic?" It will become meaningful after external dependencies exist.

## 11. Why logging is preferable to print()

Logging has levels, timestamps, logger names, and configurable handlers. Operators can filter or redirect logs without changing application code. `print()` has none of those operational controls and is difficult to manage consistently.

## 12. What pytest provides

Pytest discovers tests, runs assertions, and reports failures. The health test is deliberately small: it proves the application can create a client, route a request, return HTTP 200, and preserve the expected response shape.

## 13. What linting and formatting mean

Formatting gives the code a consistent layout automatically. Linting catches likely defects and style problems before review. Ruff provides both jobs quickly. MyPy is configured as an optional static type checker; it reasons about type annotations without running the application.

## 14. Why PostgreSQL, Kafka, and microservices are not here yet

Those tools solve real problems, but they also add operational and conceptual cost. Phase 0 has no persistent data, asynchronous events, scaling boundary, or independently deployable service that needs them. Introducing them now would hide the fundamentals and create configuration that has no job yet. Later phases will add each technology when a demonstrated requirement justifies it.

## Decision record: Pydantic Settings

- **What:** Typed configuration management built on Pydantic.
- **Why:** It separates settings from application logic and validates values at startup.
- **Problem solved:** Hardcoded environment-specific behavior becomes unsafe and difficult to change.
- **Alternative:** Direct `os.environ` access or `python-dotenv`; both require more manual parsing and validation.
- **Future:** Production secret injection and deployment-specific settings can use the same typed boundary.

## Decision record: standard logging

- **What:** Python's built-in `logging` package with one application configuration.
- **Why:** It provides levels and structured routing without another dependency.
- **Problem solved:** Application events need consistent, configurable output.
- **Alternative:** A third-party logging library; that may become useful when observability requirements grow.
- **Future:** Logs can later be emitted as structured records and collected by an observability platform.
