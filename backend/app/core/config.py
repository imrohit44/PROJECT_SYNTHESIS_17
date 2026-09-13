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
    jwt_secret: str = Field(
        default="change-this-development-secret",
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object for the application process."""

    return Settings()
