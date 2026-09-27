from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    app_name: str = Field(default="PyBank", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+psycopg://pybank:pybank@localhost:5432/pybank",
        validation_alias="DATABASE_URL",
    )
    # Phase 17 hardening: TokenService refuses secrets shorter than 32
    # characters, so even the development default must clear that floor.
    # Production overrides this via docker-compose.prod.yml, which fails fast
    # when JWT_SECRET is unset. Generate a real secret with: openssl rand -hex 32
    jwt_secret: str = Field(
        default="change-this-development-secret-min-32-chars",
        validation_alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_minutes: int = Field(
        default=15, validation_alias="ACCESS_TOKEN_MINUTES"
    )
    refresh_token_days: int = Field(default=7, validation_alias="REFRESH_TOKEN_DAYS")
    password_min_length: int = Field(default=8, validation_alias="PASSWORD_MIN_LENGTH")
    login_rate_limit: int = Field(default=5, validation_alias="LOGIN_RATE_LIMIT")
    login_rate_window_seconds: int = Field(
        default=60, validation_alias="LOGIN_RATE_WINDOW_SECONDS"
    )
    frontend_origin: str = Field(
        default="http://localhost:5173", validation_alias="FRONTEND_ORIGIN"
    )
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    cache_enabled: bool = Field(default=True, validation_alias="CACHE_ENABLED")
    customer_cache_ttl_seconds: int = Field(
        default=300, validation_alias="CUSTOMER_CACHE_TTL_SECONDS"
    )
    account_cache_ttl_seconds: int = Field(
        default=60, validation_alias="ACCOUNT_CACHE_TTL_SECONDS"
    )
    account_list_cache_ttl_seconds: int = Field(
        default=60, validation_alias="ACCOUNT_LIST_CACHE_TTL_SECONDS"
    )
    kafka_enabled: bool = Field(default=False, validation_alias="KAFKA_ENABLED")
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic_prefix: str = Field(
        default="pybank", validation_alias="KAFKA_TOPIC_PREFIX"
    )
    kafka_consumer_group: str = Field(
        default="pybank-audit-consumer", validation_alias="KAFKA_CONSUMER_GROUP"
    )
    otel_tracing_enabled: bool = Field(
        default=False, validation_alias="OTEL_TRACING_ENABLED"
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    # --- Phase 14: LLM banking assistant (optional, read-only) ---
    llm_provider: str = Field(default="", validation_alias="LLM_PROVIDER")
    llm_model: str = Field(default="", validation_alias="LLM_MODEL")
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1", validation_alias="LLM_BASE_URL"
    )
    llm_timeout_seconds: float = Field(
        default=20.0, validation_alias="LLM_TIMEOUT_SECONDS"
    )
    llm_max_output_tokens: int = Field(
        default=512, validation_alias="LLM_MAX_OUTPUT_TOKENS"
    )
    max_tool_calls_per_request: int = Field(
        default=3, validation_alias="LLM_MAX_TOOL_CALLS"
    )
    max_assistant_message_length: int = Field(
        default=2000, validation_alias="ASSISTANT_MAX_INPUT_CHARS"
    )
    assistant_rate_limit: int = Field(
        default=10, validation_alias="ASSISTANT_RATE_LIMIT"
    )
    assistant_rate_window_seconds: int = Field(
        default=60, validation_alias="ASSISTANT_RATE_WINDOW_SECONDS"
    )
    fraud_service_url: str = Field(
        default="http://fraud:8000", validation_alias="FRAUD_SERVICE_URL"
    )
    fraud_service_timeout_seconds: float = Field(
        default=5.0, validation_alias="FRAUD_SERVICE_TIMEOUT_SECONDS"
    )

    # --- Phase 15: Real-time WebSockets & WhatsApp Notifications ---
    realtime_consumer_group: str = Field(
        default="pybank-realtime-consumer",
        validation_alias="REALTIME_CONSUMER_GROUP",
    )
    # The WebSocket handshake cannot carry an Authorization header, so the JWT is
    # exchanged for a short-lived single-use ticket. Keeping it brief limits the
    # window in which a ticket captured from a log could be replayed.
    websocket_ticket_ttl_seconds: int = Field(
        default=30,
        validation_alias="WEBSOCKET_TICKET_TTL_SECONDS",
        ge=5,
        le=300,
    )
    whatsapp_enabled: bool = Field(default=False, validation_alias="WHATSAPP_ENABLED")
    whatsapp_provider: str = Field(
        default="cloud_api", validation_alias="WHATSAPP_PROVIDER"
    )
    whatsapp_api_url: str = Field(
        default="https://graph.facebook.com/v18.0",
        validation_alias="WHATSAPP_API_URL",
    )
    whatsapp_access_token: str = Field(
        default="", validation_alias="WHATSAPP_ACCESS_TOKEN"
    )
    whatsapp_phone_number_id: str = Field(
        default="", validation_alias="WHATSAPP_PHONE_NUMBER_ID"
    )
    whatsapp_sender_id: str = Field(default="", validation_alias="WHATSAPP_SENDER_ID")
    whatsapp_timeout_seconds: float = Field(
        default=5.0, validation_alias="WHATSAPP_TIMEOUT_SECONDS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object for the application process."""

    return Settings()
