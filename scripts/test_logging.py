#!/usr/bin/env python3
"""
Test script to generate various log messages for Loki testing.
"""

import logging
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from luthien_control.core.logging import setup_logging


def test_logging():
    """Generate various log messages to test Loki integration."""
    # Setup logging
    setup_logging()

    logger = logging.getLogger(__name__)

    # Generate different log levels
    logger.debug("Debug message - Testing Loki integration")
    logger.info("Info message - Application started successfully")
    logger.warning("Warning message - This is a test warning")
    logger.error("Error message - This is a test error (not a real error)")

    # Generate some structured logs
    logger.info("Processing request", extra={"request_id": "test-123", "method": "GET", "path": "/test", "status": 200})

    # Simulate some application activity
    for i in range(5):
        logger.info(f"Processing item {i + 1}/5")
        time.sleep(1)

    logger.info("Test logging completed successfully")


if __name__ == "__main__":
    test_logging()
