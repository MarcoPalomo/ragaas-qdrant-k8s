"""Structured logging configuration."""

import logging
import sys
from typing import Optional

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["service"] = settings.app_name
        log_record["version"] = settings.app_version

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure structured JSON logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = level or settings.log_level

    # Create formatter
    formatter = CustomJsonFormatter(
        fmt="%(timestamp)s %(level)s %(name)s %(message)s",
        rename_fields={"timestamp": "time"},
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stdout handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding temporary log context."""

    def __init__(self, logger: logging.Logger, **kwargs):
        """
        Initialize log context.

        Args:
            logger: Logger to add context to
            **kwargs: Additional context fields
        """
        self.logger = logger
        self.context = kwargs
        self._old_factory = None

    def __enter__(self):
        """Add context to log records."""
        old_factory = logging.getLogRecordFactory()
        context = self.context

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            for key, value in context.items():
                setattr(record, key, value)
            return record

        self._old_factory = old_factory
        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, *args):
        """Remove context from log records."""
        if self._old_factory:
            logging.setLogRecordFactory(self._old_factory)


def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **extra,
) -> None:
    """
    Log an HTTP request.

    Args:
        logger: Logger instance
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **extra: Additional fields to log
    """
    logger.info(
        f"{method} {path} - {status_code}",
        extra={
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "duration_ms": duration_ms,
            **extra,
        },
    )
