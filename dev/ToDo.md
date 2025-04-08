# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.

- [ ] ...

- Create integration tests for database logging functionality:
  - Use `test_db_session` fixture from `conftest.py`.
  - Test should call `log_request_response` (or the relevant part of the proxy if logging is integrated there).
  - Verify data insertion by querying the temporary database.

- [ ] Rework `dev/ProjectPlan.md`:
    - Reorganize sections based on current status and near-term goals (e.g., Testing Framework, Pipeline Refactor).
    - Clarify distinction between major phases and specific tasks.
    - Ensure alignment with overall project vision.