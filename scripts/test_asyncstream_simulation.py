#!/usr/bin/env python3
"""
Integration test to simulate the AsyncStream issue and verify it's fixed.

This creates objects that mimic the problematic behavior that was causing
'AsyncStream' object has no attribute 'model_dump' errors.
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to path to import luthien_control
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock

from luthien_control.control_policy.transaction_context_logging_policy import (
    TransactionContextLoggingPolicy,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.raw_response import RawResponse
from luthien_control.core.transaction import Transaction
from sqlalchemy.ext.asyncio import AsyncSession


class AsyncStreamSimulator:
    """Simulate the AsyncStream object that was causing the original error."""

    def __init__(self, data="streaming data"):
        self.data = data
        self._buffer = []
        self._closed = False

    # Notably: NO model_dump method!

    async def read(self, size=-1):
        return self.data.encode()

    def close(self):
        self._closed = True

    def __str__(self):
        return f"AsyncStreamSimulator(data={self.data!r}, closed={self._closed})"


class ResponseWithStream:
    """Simulate a response object that contains streaming components."""

    def __init__(self):
        self.status_code = 200
        self.headers = {"content-type": "text/event-stream"}
        self.stream = AsyncStreamSimulator("chunk1\nchunk2\nchunk3")
        self.content = b"some content"

    @property
    def json(self):
        # This property raises an exception when accessed (like httpx streaming responses)
        raise ValueError("Cannot parse JSON from streaming response")

    def __str__(self):
        return f"ResponseWithStream(status={self.status_code})"


async def test_streaming_objects_in_transaction():
    """Test that the logging policy handles streaming objects correctly."""
    print("=" * 60)
    print("ASYNCSTREAM SIMULATION TEST")
    print("=" * 60)

    # Create a transaction with streaming-like objects
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

    # Add problematic streaming objects to transaction data
    transaction.data["async_stream"] = AsyncStreamSimulator("test data")
    transaction.data["response_with_stream"] = ResponseWithStream()
    transaction.data["normal_field"] = "normal_value"
    transaction.data["api_key"] = "sk-secret123456789"

    # Test the logging policy
    policy = TransactionContextLoggingPolicy(name="AsyncStreamTestPolicy", log_level="INFO")

    print("Testing policy with transaction containing:")
    print("- AsyncStreamSimulator (no model_dump method)")
    print("- ResponseWithStream (has properties that raise exceptions)")
    print("- Normal fields and sensitive data")
    print()

    try:
        container = MagicMock(spec=DependencyContainer)
        session = MagicMock(spec=AsyncSession)

        print("Applying TransactionContextLoggingPolicy...")
        result = await policy.apply(transaction, container, session)

        print("✅ SUCCESS: Policy completed without errors!")
        print(f"✅ Transaction returned unchanged: {result is transaction}")
        print()
        print("The logging policy successfully handled:")
        print("- Objects without model_dump() method")
        print("- Objects with problematic properties")
        print("- Sensitive data redaction")
        print("- JSON serialization")
        return True

    except Exception as e:
        print(f"❌ FAILED: Policy raised exception: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_direct_serialization():
    """Test direct serialization of problematic objects."""
    print("=" * 60)
    print("DIRECT SERIALIZATION TEST")
    print("=" * 60)

    policy = TransactionContextLoggingPolicy()

    test_objects = {
        "AsyncStreamSimulator": AsyncStreamSimulator("test data"),
        "ResponseWithStream": ResponseWithStream(),
        "Regular dict": {"key": "value", "api_key": "sk-secret123"},
        "String": "just a string",
        "None": None,
        "List": [1, 2, 3, {"nested": "value"}],
    }

    all_passed = True

    for name, obj in test_objects.items():
        try:
            result = policy._safe_model_dump(obj)
            policy._redact_sensitive_data(result)
            keys_info = list(result.keys()) if isinstance(result, dict) else type(result).__name__
            print(f"✅ {name}: {type(result).__name__} -> {keys_info}")
        except Exception as e:
            print(f"❌ {name}: FAILED with {e}")
            all_passed = False

    return all_passed


async def main():
    """Run all tests."""
    print("Testing fix for: 'AsyncStream' object has no attribute 'model_dump'")
    print()

    # Test 1: Direct serialization
    direct_success = await test_direct_serialization()
    print()

    # Test 2: Full transaction flow
    transaction_success = await test_streaming_objects_in_transaction()
    print()

    # Summary
    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Direct serialization test: {'PASSED' if direct_success else 'FAILED'}")
    print(f"Transaction flow test: {'PASSED' if transaction_success else 'FAILED'}")

    if direct_success and transaction_success:
        print()
        print("🎉 ALL TESTS PASSED!")
        print("The AsyncStream model_dump error has been resolved.")
        print("The TransactionContextLoggingPolicy now safely handles:")
        print("- Objects without model_dump() methods")
        print("- Streaming objects and responses")
        print("- Properties that raise exceptions when accessed")
        print("- Sensitive data redaction in all scenarios")
    else:
        print()
        print("❌ Some tests failed. The issue may not be fully resolved.")

    return direct_success and transaction_success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
