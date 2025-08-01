# Test and Debug Scripts

This directory contains various test and debugging scripts used during development. These scripts are kept for future debugging needs.

## Streaming Debug Scripts

### capture_raw_openai_stream.py
- **Purpose**: Captures raw OpenAI streaming responses directly via HTTP
- **Use Case**: Debugging streaming format issues, understanding SSE format
- **Usage**: `poetry run python scripts/capture_raw_openai_stream.py`
- **Output**: JSON file with raw streaming data

### debug_openai_responses.py
- **Purpose**: Compares OpenAI streaming vs non-streaming responses
- **Use Case**: Debugging differences between response formats
- **Usage**: `poetry run python scripts/debug_openai_responses.py`
- **Output**: JSON file with comparison data

### test_streaming_logging.py
- **Purpose**: Tests streaming response logging with TransactionContextLoggingPolicy
- **Use Case**: Debugging streaming issues with logging policies
- **Usage**: `poetry run python scripts/test_streaming_logging.py`

### test_asyncstream_simulation.py
- **Purpose**: Simulates async streaming behavior for testing
- **Use Case**: Testing streaming infrastructure without making API calls

## Logging Test Scripts

### test_logging.py
- **Purpose**: Simple script to test logging configuration
- **Use Case**: Verifying logging setup is working correctly
- **Usage**: `poetry run python scripts/test_logging.py`

### test_loki_logging.py
- **Purpose**: Tests Loki logging integration
- **Use Case**: Verifying Loki handler is working when LOKI_URL is set
- **Usage**: `LOKI_URL=http://localhost:3100 poetry run python scripts/test_loki_logging.py`

## Server Startup Scripts

### start_dev_server_with_logging.py
- **Purpose**: Starts dev server with enhanced logging for debugging
- **Use Case**: Debugging streaming issues with detailed logging enabled
- **Usage**: `poetry run python scripts/start_dev_server_with_logging.py`

## Notes

- These scripts are kept for debugging purposes and are not part of the main application
- They may require environment variables to be set (check script comments)
- Some scripts create output files in the current directory