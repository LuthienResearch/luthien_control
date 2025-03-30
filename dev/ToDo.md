# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.

- [ ] ...

- Create integration tests for database logging functionality:
  - Use `test_db_session` fixture from `conftest.py`.
  - Test should call `log_request_response` (or the relevant part of the proxy if logging is integrated there).
  - Verify data insertion by querying the temporary database.

- Handle compressed backend responses for logging:
  - Check `Content-Encoding` header from backend response (e.g., gzip, deflate, br).
  - If compressed, decompress the response body before passing it to the logging function.
  - Ensure the original (potentially compressed) response is still streamed back to the client.
