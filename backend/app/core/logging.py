import logging
import logging.config

from backend.app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure standard-library logging for the application."""

    level = settings.log_level.upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s - %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stderr",
                }
            },
            "root": {"level": level, "handlers": ["default"]},
        }
    )
