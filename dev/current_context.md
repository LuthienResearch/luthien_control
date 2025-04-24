# Current Task: Completed - Refactor Dependencies Phase 2

**Goal:** Complete Phase 2 (Dependency Injection Container) of the plan defined in `dev/refactor_dependency_injection.md`.

**Status:**
*   Successfully refactored core components and tests to use the `DependencyContainer`.
*   Resolved all associated test failures in:
    *   `tests/control_policy/test_add_api_key_header.py`
    *   `tests/control_policy/test_send_backend_request.py`
    *   `tests/db/test_policy_loading.py`
    *   Other files updated in previous steps (e.g., `tests/proxy/test_orchestration.py`, `tests/proxy/test_server.py`, `tests/test_dependencies.py`).
*   All tests (`poetry run pytest`) are passing (131 passed).
*   Phase 2 is complete.

**Next Step:**
*   Commit changes.
*   Define and begin next development task (e.g., Phase 3 if applicable, or other items from `dev/ToDo.md`).

**Original Plan Reference (from `refactor_dependency_injection.md`):**
1.  Define `DependencyContainer`