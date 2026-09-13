import logging

logger = logging.getLogger("pybank.security")


def security_event(event: str, **fields: str) -> None:
    safe_fields = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("security_event=%s %s", event, safe_fields)
