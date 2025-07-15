# Centralized logging configuration for the luthien_control package.

import logging
import os
import sys
from urllib.parse import urlparse

from luthien_control.settings import Settings

# Recommended format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Default level if LOG_LEVEL env var is not set
DEFAULT_LOG_LEVEL = "INFO"

# Valid log levels
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Libraries known to be noisy that we might want to quiet down
NOISY_LIBRARIES = ["httpx", "httpcore"]


def _get_loki_handler(loki_url: str, app_name: str = "luthien_control"):
    """
    Create a Loki handler if python-logging-loki is available.

    Args:
        loki_url: URL of the Loki service
        app_name: Application name to use in Loki labels

    Returns:
        LokiHandler instance or None if not available
    """
    try:
        from logging_loki import LokiHandler

        # Parse URL to ensure it's valid
        parsed = urlparse(loki_url)
        if not parsed.scheme or not parsed.netloc:
            logging.getLogger(__name__).warning(f"Invalid Loki URL: {loki_url}")
            return None

        # Create handler with basic labels
        handler = LokiHandler(
            url=f"{loki_url}/loki/api/v1/push",
            tags={"application": app_name, "environment": os.getenv("ENVIRONMENT", "development")},
            version="1",
        )
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        return handler
    except ImportError:
        logging.getLogger(__name__).debug("python-logging-loki not available, skipping Loki handler")
        return None
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to create Loki handler: {e}")
        return None


def setup_logging():
    """
    Configures logging for the application.

    Reads the desired log level from the LOG_LEVEL environment variable.
    Defaults to INFO if not set or invalid.
    Sets a standard format and directs logs to stderr.
    Sets louder libraries to WARNING level.
    Optionally configures Loki handler if LOKI_URL is set.
    """
    settings = Settings()
    log_level_name = settings.get_log_level(default=DEFAULT_LOG_LEVEL)

    if log_level_name not in VALID_LOG_LEVELS:
        print(
            f"WARNING: Invalid LOG_LEVEL '{log_level_name}'. "
            f"Defaulting to {DEFAULT_LOG_LEVEL}. "
            f"Valid levels are: {', '.join(VALID_LOG_LEVELS)}",
            file=sys.stderr,
        )
        log_level_name = DEFAULT_LOG_LEVEL

    log_level = logging.getLevelName(log_level_name)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)

    # Loki handler if configured
    loki_url = os.getenv("LOKI_URL")
    if loki_url:
        loki_handler = _get_loki_handler(loki_url)
        if loki_handler:
            root_logger.addHandler(loki_handler)
            logging.getLogger(__name__).info(f"Loki logging configured for {loki_url}")

    # Quiet down noisy libraries
    for lib_name in NOISY_LIBRARIES:
        logging.getLogger(lib_name).setLevel(logging.WARNING)

    # Log that configuration is complete (useful for debugging setup issues)
    logging.getLogger(__name__).info(f"Logging configured with level {log_level_name}.")
