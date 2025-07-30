# E2E Streaming Tests

This document describes the end-to-end tests for streaming response functionality in Luthien Control.

## Overview

The streaming E2E tests verify that the proxy correctly handles OpenAI streaming responses, including:
- Server-Sent Events (SSE) formatting
- Proper chunk processing through the policy chain
- Error handling during streaming
- Client disconnection scenarios
- Concurrent streaming requests

## Test Coverage

### Basic Streaming Tests
- **test_streaming_chat_completion_file_based**: Verifies basic streaming functionality with file-based policy configuration
- **test_streaming_chat_completion_db_based**: Verifies streaming with database-based policy configuration

### Compatibility Tests
- **test_non_streaming_still_works_file_based**: Ensures non-streaming requests continue to work correctly

### Edge Cases
- **test_streaming_with_early_client_disconnect**: Tests behavior when client disconnects mid-stream
- **test_streaming_with_invalid_model**: Verifies error handling for invalid requests
- **test_concurrent_streaming_requests**: Tests multiple simultaneous streaming requests
- **test_streaming_with_large_response**: Verifies chunking works correctly for large responses

## Running the Tests

### Prerequisites
1. Set environment variables:
   ```bash
   export OPENAI_API_KEY=your_key_here
   export TEST_CLIENT_API_KEY=test_client_key
   ```

2. Ensure the database is set up (for DB-based tests):
   ```bash
   poetry run python -m luthien_control.db.init_db
   ```

### Run All E2E Tests
```bash
poetry run pytest -m e2e
```

### Run Only Streaming E2E Tests
```bash
poetry run pytest tests/e2e/test_streaming_e2e.py -v
```

### Run Against External Server
```bash
poetry run pytest tests/e2e/test_streaming_e2e.py --e2e-target-url=https://your-server.com -v
```

## Test Implementation Details

### SSE Event Collection
The tests use a custom `collect_sse_events()` function to properly parse Server-Sent Events from the streaming response. This function:
- Handles partial chunks
- Parses JSON data from SSE format
- Detects the `[DONE]` termination event
- Handles malformed data gracefully

### Expected Response Format
Streaming responses should follow the OpenAI SSE format:
```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo",...}
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo",...}
...
data: [DONE]
```

### Headers Validation
The tests verify that streaming responses include appropriate headers:
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `Connection: keep-alive`
- `X-Accel-Buffering: no` (for Nginx compatibility)

## Known Issues

### Server-Side Streaming Issue
There is currently a known issue in the streaming implementation where the server encounters:
```
RuntimeError: Unexpected message received: http.request
```

This appears to be an ASGI protocol issue with the FastAPI StreamingResponse implementation. The issue occurs after:
1. The request is successfully processed through the policy chain
2. The OpenAI streaming response is received
3. The FastAPI StreamingResponse is created with proper headers
4. But the actual streaming fails during response transmission

**Current Test Approach**: The E2E tests currently verify that:
- Streaming requests are properly routed and processed
- Appropriate streaming headers are returned (`text/event-stream`, `no-cache`, etc.)
- The streaming infrastructure is in place

**Impact**: Streaming responses return proper headers but may not deliver actual SSE events to clients.

**Next Steps**: This issue needs to be investigated and resolved in the streaming response implementation.

## Common Issues and Troubleshooting

### Rate Limiting
If tests fail due to rate limiting:
1. Add delays between tests
2. Use a model with higher rate limits
3. Run tests individually

### Timeout Issues
For slow connections or large responses:
1. Increase the httpx client timeout in conftest.py
2. Reduce `max_tokens` in test payloads

### Authentication Failures
Ensure both `OPENAI_API_KEY` and `TEST_CLIENT_API_KEY` are set correctly in your environment.

## Future Enhancements

Potential improvements to the streaming E2E tests:
1. Add tests for streaming with function calling
2. Test streaming with different models (GPT-4, etc.)
3. Add performance benchmarks for streaming latency
4. Test streaming with various client libraries
5. Add tests for streaming token usage tracking