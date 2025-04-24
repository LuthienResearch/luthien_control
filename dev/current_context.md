# Current Task: Refactor Dependencies Phase 2 - Fix Test Failures

**Goal:** Implement a centralized Dependency Injection Container for core shared services (Settings, HTTP Client, DB Session Factory) and refactor dependencies to use it.

**Current State:**
*   Phase 2 Steps 7-12 completed (Container defined, integrated into lifespan, dependency providers refactored, core logic adjusted).
*   Started Step 13: Refactor Tests.
*   Initial test refactoring for `conftest.py`, `test_dependencies.py`, `test_client_api_key_auth.py`, `test_compound_policy.py`, `test_orchestration.py`, and `test_server.py` completed.
*   Running `pytest` revealed 5 remaining test failures:
    *   `test_compound_policy.py::test_compound_policy_applies_policies_sequentially`: Assertion failure on context passed to second policy.
    *   `test_compound_policy.py::test_compound_policy_continues_on_response`: Assertion failure on final context identity.
    *   `test_orchestration.py::test_run_policy_flow_successful`: `AssertionError: Expected 'build_response' to have been called once. Called 0 times.` (Likely due to mock policy setting `context.response`).
    *   `test_orchestration.py::test_run_policy_flow_unexpected_exception`: `AttributeError: 'TransactionContext' object has no attribute 'exception'` (Assertion needs removal).
    *   `test_server.py::test_api_proxy_endpoint_handles_post`: `AssertionError: assert 500 == 200` (Underlying `AttributeError: 'coroutine' object has no attribute 'name'` from patched `load_policy_from_db`).

**Next Action:** Address the 5 remaining test failures, starting with the two in `tests/control_policy/test_compound_policy.py`.
