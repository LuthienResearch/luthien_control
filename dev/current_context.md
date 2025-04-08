# Current Task
## Remove pydantic-settings Dependency
 - Status: Complete
 - Major changes made:
    - Removed `pydantic-settings` dependency.
    - Refactored configuration loading in `luthien_control/config/settings.py`, `luthien_control/db/database.py`, `luthien_control/proxy/server.py`, `luthien_control/policy_loader.py` to use `os.getenv` and `python-dotenv`.
    - Updated test fixtures and mocks in `tests/conftest.py`, `tests/db/test_database.py`, `tests/test_policy_loader.py`.
    - Fixed associated test failures.
 - Follow-up tasks, if any: None directly related to this task.
