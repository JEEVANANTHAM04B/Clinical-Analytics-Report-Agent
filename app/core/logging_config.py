"""
app/core/logging_config.py
===========================
Centralized Logging Configuration

WHY A CENTRAL LOGGING CONFIG?
    Python's logging module is powerful but messy when set up in multiple places.
    If each module configures its own logger differently, you get:
      - Duplicate log messages
      - Inconsistent formats
      - Hard to control log levels globally

    Our approach:
      - One setup_logging() function called ONCE at startup (in main.py)
      - Every module creates its own named logger: logger = get_logger(__name__)
      - All loggers inherit the root configuration set here
      - Easy to switch between development (text) and production (JSON) formats

FUTURE USE:
    This same logger will be used by:
      - Data ingestion module
      - MySQL query layer
      - RAG retrieval pipeline
      - LangChain/LangGraph agents
      - SQL validation layer
      - Plotly chart generation
      - PDF report generation
      - Audit logging (Phase 7+)
"""

import logging
import sys
from datetime import datetime
from app.config import settings


# =============================================================================
# Log Format Definitions
# =============================================================================

# Text format — human-readable, great for development
TEXT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

# Date format for text logs
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class JSONFormatter(logging.Formatter):
    """
    Custom JSON log formatter for production/structured logging.

    WHY JSON LOGS?
        In production, logs are often ingested by log aggregation tools
        (like Datadog, Splunk, or AWS CloudWatch). JSON format makes
        it easy to filter, search, and alert on specific fields.

    Example output:
        {"timestamp": "2024-01-15 10:30:45", "level": "INFO",
         "logger": "app.core.database", "message": "MySQL connected",
         "environment": "production"}
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": settings.ENVIRONMENT,
        }

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


# =============================================================================
# Setup Function — Called ONCE at application startup
# =============================================================================

def setup_logging() -> None:
    """
    Configure the root logger for the entire application.

    Call this ONCE at startup in main.py.
    After calling this, all loggers created with get_logger() will
    automatically inherit this configuration.

    Reads from settings:
        LOG_LEVEL  — Controls verbosity (DEBUG shows everything, ERROR shows only errors)
        LOG_FORMAT — "text" for human-readable, "json" for structured production logs
    """

    # Get log level from settings (e.g., "INFO" → logging.INFO = 20)
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Choose formatter based on config
    if settings.LOG_FORMAT == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(fmt=TEXT_FORMAT, datefmt=DATE_FORMAT)

    # Set up console handler — outputs to stdout (terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Configure the ROOT logger
    # All loggers in the app are children of this root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers (prevents duplicate messages on reload)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Silence noisy third-party loggers in development
    # These libraries log a lot of internal detail we don't need to see
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    # Log confirmation that logging is ready
    logger = get_logger(__name__)
    logger.info(
        f"Logging initialized | level={settings.LOG_LEVEL} | "
        f"format={settings.LOG_FORMAT} | env={settings.ENVIRONMENT}"
    )


# =============================================================================
# Logger Factory — Used by every module in the project
# =============================================================================

def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger for a specific module.

    USAGE in any module:
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)

        logger.info("Processing started")
        logger.warning("Missing value in row 42")
        logger.error("MySQL connection failed", exc_info=True)

    WHY __name__?
        Using __name__ gives each logger the module's full dotted path,
        e.g., "app.core.database" or "app.api.health".
        This tells you EXACTLY where each log message came from.

    Args:
        name: Typically __name__ from the calling module.

    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(name)
