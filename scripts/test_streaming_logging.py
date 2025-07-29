#!/usr/bin/env python3
"""
Test script to debug streaming response logging with TransactionContextLoggingPolicy.

This script starts a local dev server, makes a streaming request, and observes
how the logging policy handles streaming objects in real production conditions.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the parent directory to path to import luthien_control
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from luthien_control.control_policy.transaction_context_logging_policy import (
    TransactionContextLoggingPolicy,
)

# Set up detailed logging to see what happens
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def test_streaming_request():
    """Test making a streaming request to see how objects are handled."""
    logger.info("Starting streaming request test...")

    # Configuration for local dev server
    base_url = "http://localhost:8000"  # Adjust port if different

    # Test payload for streaming chat completion
    test_payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Write a short poem about debugging"}],
        "stream": True,  # This should trigger streaming response
        "max_tokens": 100,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-api-key-12345",  # Test API key
    }

    try:
        logger.info(f"Making streaming request to {base_url}/v1/chat/completions")

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST", f"{base_url}/v1/chat/completions", json=test_payload, headers=headers
            ) as response:
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response headers: {dict(response.headers)}")

                # Read the streaming response
                chunks = []
                async for chunk in response.aiter_text():
                    chunks.append(chunk)
                    logger.debug(f"Received chunk: {chunk[:100]}...")

                    # Stop after a few chunks to avoid too much output
                    if len(chunks) >= 3:
                        break

                logger.info(f"Received {len(chunks)} chunks total")

                # Test how our logging policy would handle the response object
                logger.info("Testing TransactionContextLoggingPolicy serialization...")
                policy = TransactionContextLoggingPolicy(log_level="DEBUG")

                # Try to serialize the response object directly
                try:
                    result = policy._safe_model_dump(response)
                    logger.info(f"Successfully serialized response: {result}")
                except Exception as e:
                    logger.error(f"Failed to serialize response: {e}")

                # Try to serialize some common streaming attributes
                test_objects = {
                    "response": response,
                    "stream": response.stream if hasattr(response, "stream") else None,
                    "headers": dict(response.headers) if hasattr(response, "headers") else None,
                }

                for name, obj in test_objects.items():
                    if obj is not None:
                        try:
                            result = policy._safe_model_dump(obj)
                            keys_info = list(result.keys()) if isinstance(result, dict) else "not dict"
                            logger.info(f"Successfully serialized {name}: {type(result)} with keys {keys_info}")
                        except Exception as e:
                            logger.error(f"Failed to serialize {name}: {e}")

    except httpx.ConnectError:
        logger.error(f"Could not connect to {base_url}. Make sure the dev server is running.")
        logger.info("To start the dev server, run: poetry run uvicorn luthien_control.main:app --reload --port 8000")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during streaming test: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False

    return True


async def test_policy_with_mock_transaction():
    """Test the policy with a mock transaction containing streaming-like objects."""
    logger.info("Testing policy with mock streaming transaction...")

    from luthien_control.core.raw_request import RawRequest
    from luthien_control.core.raw_response import RawResponse
    from luthien_control.core.transaction import Transaction

    # Create a mock streaming object that might cause issues
    class MockStreamingResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "text/event-stream"}
            self.content = b"data: streaming content"
            # Simulate an object that doesn't have model_dump

        def __str__(self):
            return f"MockStreamingResponse(status={self.status_code})"

    # Create a transaction with potentially problematic objects
    raw_request = RawRequest(
        method="POST",
        path="/v1/chat/completions",
        api_key="sk-test123456789",
        headers={"Authorization": "Bearer secret-token"},
        body=b'{"model": "gpt-4", "stream": true}',
    )

    raw_response = RawResponse(
        status_code=200, headers={"content-type": "text/event-stream"}, body=b"data: streaming response"
    )

    transaction = Transaction(raw_request=raw_request, raw_response=raw_response)

    # Add some problematic data to the transaction
    transaction.data["streaming_object"] = MockStreamingResponse()
    transaction.data["normal_field"] = "normal_value"
    transaction.data["api_key"] = "sk-secret123456789"

    # Test the policy
    policy = TransactionContextLoggingPolicy(name="StreamingTestPolicy", log_level="DEBUG")

    try:
        from unittest.mock import MagicMock

        from luthien_control.core.dependency_container import DependencyContainer
        from sqlalchemy.ext.asyncio import AsyncSession

        container = MagicMock(spec=DependencyContainer)
        session = MagicMock(spec=AsyncSession)

        logger.info("Applying TransactionContextLoggingPolicy to mock transaction...")
        result = await policy.apply(transaction, container, session)

        logger.info(f"Policy completed successfully. Transaction returned: {result is transaction}")
        return True

    except Exception as e:
        logger.error(f"Policy failed with error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("STREAMING RESPONSE LOGGING DEBUG TEST")
    logger.info("=" * 60)

    # Test 1: Mock transaction with streaming-like objects
    logger.info("\n" + "=" * 40)
    logger.info("TEST 1: Mock Transaction with Streaming Objects")
    logger.info("=" * 40)

    mock_success = await test_policy_with_mock_transaction()

    # Test 2: Real streaming request (if server is available)
    logger.info("\n" + "=" * 40)
    logger.info("TEST 2: Real Streaming Request")
    logger.info("=" * 40)

    real_success = await test_streaming_request()

    # Summary
    logger.info("\n" + "=" * 40)
    logger.info("TEST SUMMARY")
    logger.info("=" * 40)
    logger.info(f"Mock transaction test: {'PASSED' if mock_success else 'FAILED'}")
    logger.info(f"Real streaming test: {'PASSED' if real_success else 'FAILED'}")

    if mock_success and real_success:
        logger.info("All tests passed! The logging policy should handle streaming correctly.")
    else:
        logger.warning("Some tests failed. Check the logs above for details.")

    return mock_success and real_success


if __name__ == "__main__":
    asyncio.run(main())
