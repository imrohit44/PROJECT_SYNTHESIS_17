FROM python:3.12-slim

WORKDIR /app

# Install system dependencies needed for confluent-kafka and psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    librdkafka-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Build context is the repository root so the shared services/common package
# (whose observability and tracing modules the fraud service imports) can be
# copied into the image. The fraud service stays independently deployable: it
# has its own pyproject.toml, alembic directory and entrypoint.
COPY services/common ./services/common
COPY services/fraud/pyproject.toml ./services/fraud/pyproject.toml
COPY services/fraud/alembic.ini ./services/fraud/alembic.ini
COPY services/fraud/alembic ./services/fraud/alembic
COPY services/fraud/app ./services/fraud/app
COPY services/fraud/ml ./services/fraud/ml
COPY services/fraud/models ./services/fraud/models
COPY services/fraud/tests ./services/fraud/tests
COPY docker/fraud-entrypoint.sh ./docker/fraud-entrypoint.sh

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ./services/fraud \
    && chmod +x /app/docker/fraud-entrypoint.sh

# /app makes services.common importable; /app/services/fraud makes `app.*`
# importable by the fraud application and by its alembic migrations.
ENV PYTHONPATH=/app/services/fraud:/app

EXPOSE 8000

ENTRYPOINT ["/app/docker/fraud-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
