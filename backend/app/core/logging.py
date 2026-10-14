"""JSON logging to stderr without recording request bodies or credentials."""

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, str | int | float] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("method", "status_code", "duration_ms"):
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        return json.dumps(entry)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("aktrace")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
