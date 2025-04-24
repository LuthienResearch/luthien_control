# Current Task: Refactor Dependencies Phase 2 - Debug Test Failures

**Goal:** Implement Phase 2 (Dependency Injection Container) of the plan defined in `dev/refactor_dependency_injection.md`.

**Overall Plan:**
1.  Define `DependencyContainer` (Done).
2.  Integrate into Lifespan (Done).
3.  Create Container Dependency (`get_dependencies`) (Done).
4.  Refactor Dependency Providers (`get_settings`, `get_http_client`, `get_db_session`) (Done).
5.  Refactor `get_main_control_policy` (Done).
6.  Refactor Core Logic (`load_policy_from_db`) (Done).
7.  Refactor Policy `apply` Signatures (`ClientApiKeyAuthPolicy`, `CompoundPolicy`) (Done).
8.  Update Base `ControlPolicy.apply` signature (Done - Step 11.5).
9.  Update API Route (`proxy/server.py`) signature and `apply` call (Done - Step 12).
10. Update Orchestration Function (`proxy/orchestration.py`) signature and `apply` call (Done - Step 12.5).
11. Refactor Tests (`tests/`) (Partially Done - Step 13).

**Current State:**
*   Steps 7-12.5 of the plan are complete. Code changes applied, including updating `apply` signatures and API/orchestration logic.
*   Test Refactoring (Step 13) was attempted:
    *   Initial fixes applied successfully to `test_compound_policy.py`, `test_policy_loading.py`, `test_dependencies.py`, `test_client_api_key_auth.py`.
    *   Refactoring `tests/proxy/test_orchestration.py` to align with the new `run_policy_flow` signature (passing container/session, removing builder) introduced errors.
*   **Rollback:** Subsequent attempts to fix failures in `tests/proxy/test_orchestration.py` (modifying `mock_policy` fixture, changing `await_args` to `call_args`) were unsuccessful and have been **rolled back**. The code is now in the state immediately after the initial refactoring of `test_orchestration.py`.
*   Running `pytest` in the current state results in 6 failures:
    *   `tests/proxy/test_orchestration.py::test_run_policy_flow_successful` (`IndexError: tuple index out of range` on `await_args` assertion)
    *   `tests/proxy/test_orchestration.py::test_run_policy_flow_policy_exception` (`IndexError: tuple index out of range` on `await_args` assertion)
    *   `tests/proxy/test_orchestration.py::test_run_policy_flow_unexpected_exception` (`IndexError: tuple index out of range` on `await_args` assertion)
    *   `tests/proxy/test_orchestration.py::test_run_policy_flow_unexpected_exception_during_build` (`RuntimeError: Builder failed!`)
    *   `tests/proxy/test_orchestration.py::test_run_policy_flow_context_init_exception` (`ValueError: Context creation failed!`)
    *   `tests/proxy/test_server.py::test_api_proxy_endpoint_calls_orchestrator` (`AssertionError: assert 'builder' in {...}`)

**Next Action:**
1.  Run `pytest` to confirm the 6 failures listed above are present after the rollback.
2.  Debug the failures in `test_orchestration.py` and `test_server.py` systematically. Start with the `test_server.py` failure as it seems simpler.
