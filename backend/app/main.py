import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.api.errors import register_exception_handlers
from backend.app.api.v1.router import router as api_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.infrastructure.kafka import (
    AuditConsumer,
    AuditConsumerThread,
    KafkaEventProducer,
    OutboxPublisher,
    OutboxPublisherThread,
)
from backend.app.infrastructure.outbox import OutboxRepository
from backend.app.infrastructure.persistence.database import create_session_factory

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s in %s environment", settings.app_name, settings.app_env)
    workers: list[OutboxPublisherThread | AuditConsumerThread] = []
    if settings.kafka_enabled:
        session_factory = create_session_factory(settings.database_url)
        topic = f"{settings.kafka_topic_prefix}.events"
        producer = KafkaEventProducer(settings.kafka_bootstrap_servers, topic)
        workers.append(
            OutboxPublisherThread(
                OutboxPublisher(OutboxRepository(session_factory), producer)
            )
        )
        workers.append(
            AuditConsumerThread(
                AuditConsumer(
                    settings.kafka_bootstrap_servers,
                    topic,
                    settings.kafka_consumer_group,
                    session_factory,
                )
            )
        )
        for worker in workers:
            worker.start()
    yield
    for worker in workers:
        worker.stop()
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response


app.add_middleware(SecurityHeadersMiddleware)
register_exception_handlers(app)
app.include_router(api_router)
