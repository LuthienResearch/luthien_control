#!/usr/bin/env python3
"""
Start the dev server with TransactionContextLoggingPolicy enabled for debugging.

This script configures a test policy that includes the logging policy to help
debug streaming response issues.
"""

import json
import logging
from pathlib import Path

# Set up logging to see what's happening
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


def create_test_policy_config():
    """Create a test policy configuration that includes the logging policy."""

    policy_config = {
        "type": "SerialPolicy",
        "name": "StreamingTestPolicy",
        "policies": [
            {"type": "ClientApiKeyAuth", "name": "AuthPolicy"},
            {"type": "TransactionContextLoggingPolicy", "name": "StreamingDebugLogger", "log_level": "INFO"},
            {"type": "SendBackendRequest", "name": "BackendRequest"},
        ],
    }

    return policy_config


def save_policy_to_file():
    """Save the test policy to a JSON file."""
    policy_config = create_test_policy_config()

    policy_file = Path("scripts/test_streaming_policy.json")

    with open(policy_file, "w") as f:
        json.dump(policy_config, f, indent=2)

    logger.info(f"Saved test policy to: {policy_file.absolute()}")
    return policy_file


def main():
    """Main function to set up and start the server."""
    logger.info("Setting up dev server with streaming logging debug...")

    # Create the test policy file
    policy_file = save_policy_to_file()

    logger.info("Test policy configuration:")
    with open(policy_file) as f:
        policy_content = f.read()
        print(policy_content)

    logger.info("\n" + "=" * 60)
    logger.info("INSTRUCTIONS:")
    logger.info("=" * 60)
    logger.info("1. Set up your environment variables for the backend API")
    logger.info("2. Update your database with this policy configuration")
    logger.info("3. Start the server with:")
    logger.info("   poetry run uvicorn luthien_control.main:app --reload --port 8000")
    logger.info("4. In another terminal, run the streaming test:")
    logger.info("   poetry run python scripts/test_streaming_logging.py")
    logger.info("=" * 60)

    logger.info("\nAlternatively, you can manually add this policy to your database:")
    logger.info(
        "UPDATE policies SET config = '{}' WHERE name = 'your_policy_name';".format(
            json.dumps(create_test_policy_config()).replace("'", "''")
        )
    )


if __name__ == "__main__":
    main()
