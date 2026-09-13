FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/pybank/.local/bin:${PATH}"

WORKDIR /app

RUN addgroup --system pybank && adduser --system --ingroup pybank pybank

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY backend ./backend
COPY docker/backend-entrypoint.sh ./docker/backend-entrypoint.sh

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && chmod +x /app/docker/backend-entrypoint.sh \
    && chown -R pybank:pybank /app

USER pybank

EXPOSE 8000

ENTRYPOINT ["/app/docker/backend-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
