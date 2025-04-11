"""Centralized logging configuration for the luthien_control package."""

import logging
import os
import sys

# Recommended format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Default level if LOG_LEVEL env var is not set
DEFAULT_LOG_LEVEL = "INFO"

# Valid log levels
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Libraries known to be noisy that we might want to quiet down
NOISY_LIBRARIES = ["httpx", "httpcore"]


def setup_logging():
    """
    Configures logging for the application.

    Reads the desired log level from the LOG_LEVEL environment variable.
    Defaults to INFO if not set or invalid.
    Sets a standard format and directs logs to stderr.
    Sets louder libraries to WARNING level.
    """
    log_level_name = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()

    if log_level_name not in VALID_LOG_LEVELS:
        print(
            f"WARNING: Invalid LOG_LEVEL '{log_level_name}'. "
            f"Defaulting to {DEFAULT_LOG_LEVEL}. "
            f"Valid levels are: {', '.join(VALID_LOG_LEVELS)}",
            file=sys.stderr,
        )
        log_level_name = DEFAULT_LOG_LEVEL

    log_level = logging.getLevelName(log_level_name)

    # Use basicConfig for simplicity, directing to stderr
    logging.basicConfig(level=log_level, format=LOG_FORMAT, stream=sys.stderr)

    # Quiet down noisy libraries
    for lib_name in NOISY_LIBRARIES:
        logging.getLogger(lib_name).setLevel(logging.WARNING)

    # Log that configuration is complete (useful for debugging setup issues)
    logging.getLogger(__name__).info(f"Logging configured with level {log_level_name}.")


# Example of how to get a logger in other modules:
# import logging
# logger = logging.getLogger(__name__)
