"""
Tests for the TokenCounterPolicy focusing on async accuracy.
"""

import asyncio
import json
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi import Request

from luthien_control.policies.examples.token_counter import TokenCounterPolicy

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# --- Mock Data ---


# Simple mock encoder: count characters in string values
def mock_encode(text):
    return list(text)


class MockEncoding:
    def encode(self, text):
        return mock_encode(text)


# Mock request/response data assumes OpenAI chat format
MOCK_REQUEST_BODY = json.dumps(
    {"messages": [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hello world!"}]}
).encode("utf-8")
# Original calculation (overhead 4, primer +2 overall)
# msg1: 4 + 6 + 14 = 24
# msg2: 4 + 4 + 12 = 20
# Total = 24 + 20 + 2 = 46
EXPECTED_REQUEST_TOKENS = 46  # Back to 46

# Response calculation
MOCK_RESPONSE_CONTENT = json.dumps(
    {"choices": [{"message": {"role": "assistant", "content": "Response content here."}}]}
).encode("utf-8")
# len("Response content here.") = 20
EXPECTED_RESPONSE_TOKENS = 20

# --- Test Case ---


@pytest.mark.asyncio
async def test_concurrent_counting_accuracy():
    """
    Tests that TokenCounterPolicy maintains accurate counts with concurrent requests/responses.
    """
    NUM_CONCURRENT_TASKS = 100
    # Based on the logic in _count_tokens_in_messages and mocking encode to return length 1:
    # messages = [{"role": "user", "content": "hello"}] (2 keys)
    # tokens_per_msg = 4 + 2*1 = 6
    # total = tokens_per_msg + 2 = 8
    EXPECTED_REQUEST_TOKENS = 8
    # Based on mocking encode to return length 1 for response content:
    EXPECTED_RESPONSE_TOKENS = 1

    # Mock the tiktoken encoding globally for this test
    mock_encoding = Mock()
    mock_encoding.encode.return_value = [1]  # Return a list of length 1

    with patch("tiktoken.encoding_for_model", return_value=mock_encoding) as mock_get_encoding:
        policy = TokenCounterPolicy(model="gpt-3.5-turbo")  # Model choice doesn't matter due to mock

        # --- Mock Request Data ---
        mock_request_messages = [{"role": "user", "content": "hello"}]
        mock_request_body_dict = {"messages": mock_request_messages}
        mock_request_body_bytes = json.dumps(mock_request_body_dict).encode("utf-8")

        mock_request_obj = Mock(spec=Request)
        # Mock necessary attributes of the request object if policy uses them
        # (Currently, process_request doesn't seem to use request attributes directly)

        # --- Mock Response Data ---
        mock_response_content_dict = {"choices": [{"message": {"content": "world"}}]}
        mock_response_content_bytes = json.dumps(mock_response_content_dict).encode("utf-8")

        mock_response_obj = Mock(spec=httpx.Response)
        mock_response_obj.url = Mock()
        mock_response_obj.url.path = "/v1/chat/completions"  # Needs to match check in policy
        mock_response_obj.status_code = 200
        mock_response_obj.headers = {}  # Use a mutable dict

        # --- Helper Coroutines ---
        async def run_request():
            # Pass copies or new mocks if necessary, but policy state is shared
            await policy.process_request(
                request=mock_request_obj,
                target_url="https://api.example.com/v1/chat/completions",  # Needs to match check
                headers={},
                body=mock_request_body_bytes,
            )

        async def run_response():
            # Pass copies or new mocks if necessary
            await policy.process_response(
                request=mock_request_obj, response=mock_response_obj, content=mock_response_content_bytes
            )

        # --- Run Concurrently ---
        request_tasks = [asyncio.create_task(run_request()) for _ in range(NUM_CONCURRENT_TASKS)]
        response_tasks = [asyncio.create_task(run_response()) for _ in range(NUM_CONCURRENT_TASKS)]

        await asyncio.gather(*request_tasks, *response_tasks)

        # --- Assert Final Counts ---
        final_counts = policy.get_token_counts()
        expected_total_requests = NUM_CONCURRENT_TASKS * EXPECTED_REQUEST_TOKENS
        expected_total_responses = NUM_CONCURRENT_TASKS * EXPECTED_RESPONSE_TOKENS
        expected_total = expected_total_requests + expected_total_responses

        assert final_counts["requests"] == expected_total_requests
        assert final_counts["responses"] == expected_total_responses
        assert final_counts["total"] == expected_total
        # Verify the mock was called as expected
        mock_get_encoding.assert_called_once_with("gpt-3.5-turbo")
        # Check encode calls (approximate, depends on exact loops in policy)
        # Request: 1 msg * 2 keys = 2 encodes per request
        # Response: 1 encode per response
        expected_encode_calls = NUM_CONCURRENT_TASKS * 2 + NUM_CONCURRENT_TASKS * 1
        assert mock_encoding.encode.call_count == expected_encode_calls


# Example of how to run this specific test with pytest:
# poetry run pytest tests/policies/examples/test_token_counter.py::test_concurrent_counting_accuracy

# Remove TODO comment
# -# TODO: Add test cases here


@patch("luthien_control.policies.examples.token_counter.logging.error")
@patch("tiktoken.encoding_for_model")  # Mock encoding so it doesn't raise error
async def test_process_request_invalid_json(mock_encoding, mock_logger_error):
    """Test process_request handles invalid JSON gracefully."""
    policy = TokenCounterPolicy(model="gpt-3.5-turbo")
    initial_counts = policy.get_token_counts().copy()
    mock_request = Mock(spec=Request)
    invalid_body = b"this is not json"
    target_url = "https://api.example.com/v1/chat/completions"
    headers = {}

    result = await policy.process_request(
        request=mock_request, target_url=target_url, headers=headers, body=invalid_body
    )

    # Check that logging.error was called
    mock_logger_error.assert_called_once()
    assert "Error processing request tokens:" in mock_logger_error.call_args[0][0]

    # Check that counts are unchanged
    assert policy.get_token_counts() == initial_counts

    # Check that original data is returned
    assert result["target_url"] == target_url
    assert result["headers"] == headers
    assert result["body"] == invalid_body


@patch("luthien_control.policies.examples.token_counter.logging.error")
@patch("tiktoken.encoding_for_model")  # Mock encoding so it doesn't raise error
async def test_process_response_invalid_json(mock_encoding, mock_logger_error):
    """Test process_response handles invalid JSON gracefully."""
    policy = TokenCounterPolicy(model="gpt-3.5-turbo")
    initial_counts = policy.get_token_counts().copy()
    mock_request = Mock(spec=Request)
    invalid_content = b"this is not json"

    mock_response_obj = Mock(spec=httpx.Response)
    mock_response_obj.url = Mock()
    mock_response_obj.url.path = "/v1/chat/completions"  # Needs to match check in policy
    mock_response_obj.status_code = 200
    mock_response_obj.headers = {"content-type": "application/json"}  # Use a mutable dict

    result = await policy.process_response(request=mock_request, response=mock_response_obj, content=invalid_content)

    # Check that logging.error was called
    mock_logger_error.assert_called_once()
    assert "Error processing response tokens:" in mock_logger_error.call_args[0][0]

    # Check that counts are unchanged
    assert policy.get_token_counts() == initial_counts

    # Check that original data is returned
    assert result["status_code"] == mock_response_obj.status_code
    assert result["headers"] == mock_response_obj.headers
    assert result["content"] == invalid_content


@patch("tiktoken.encoding_for_model")
async def test_process_request_with_name_key(mock_encoding_for_model):
    """Test token counting when messages include the 'name' key."""
    # Setup mock encoder
    mock_encoder = Mock()
    mock_encoder.encode.return_value = [1]  # Keep it simple: length 1
    mock_encoding_for_model.return_value = mock_encoder

    policy = TokenCounterPolicy(model="gpt-test")
    mock_request = Mock(spec=Request)
    headers = {}
    target_url = "/v1/chat/completions"

    # Message list including the 'name' key
    messages_with_name = [
        {"role": "user", "content": "hello"},  # No name key
        {"name": "test_func", "role": "function", "content": "result"},  # Includes name key
    ]
    body_with_name = json.dumps({"messages": messages_with_name}).encode("utf-8")

    # Expected tokens based on _count_tokens_in_messages logic and encode returning len 1:
    # Msg 1: 4 + (role:1) + (content:1) = 6 tokens
    # Msg 2: 4 + (name:1 - 1) + (role:1) + (content:1) = 6 tokens
    # Total: msg1 + msg2 + 2 = 6 + 6 + 2 = 14 tokens
    expected_token_count = 14

    await policy.process_request(request=mock_request, target_url=target_url, headers=headers, body=body_with_name)

    final_counts = policy.get_token_counts()
    assert final_counts["requests"] == expected_token_count
    assert final_counts["total"] == expected_token_count
    assert headers["X-Request-Token-Count"] == str(expected_token_count)

    # Verify encode was called for each value (role, content, name, role, content)
    assert mock_encoder.encode.call_count == 5
