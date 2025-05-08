Last task completed: Successfully refactored and debugged initial tests in `tests/proxy/test_server.py` (`test_api_proxy_post_endpoint_calls_orchestrator`, `test_api_proxy_no_auth_policy_no_key_success`). Established a working pattern.

# Refactoring Plan: Improve Testability and Mocking Strategy

## Goal:
Simplify the mocking strategy and application setup to make tests easier to write, reason about, and maintain, ultimately aiming to improve test coverage.

## Phase 1: Refactor `luthien_control/main.py` (Completed)

1.  **Isolate Dependency Creation:** (Completed)
    *   **Action:** Create `_initialize_app_dependencies` in `luthien_control/main.py`. (Completed)
    *   **Details:** Encapsulates creation of `httpx.AsyncClient`, DB components, `DependencyContainer`.
    *   **Error Handling:** Internal error handling and resource cleanup.
    *   **Return Value:** `DependencyContainer`.

2.  **Update `lifespan` Function:** (Completed)
    *   **Action:** Modify `lifespan` in `luthien_control/main.py`. (Completed)
    *   **Details:** Calls helper, stores result, handles errors, manages global cleanup.

## Phase 2: Rework Mocking and Test Setup (In Progress)

1.  **Modify `override_app_dependencies` in `tests/conftest.py`:** (Completed)
    *   **Action:** Removed `autouse=True`. (Completed)
    *   **Rationale:** Explicit dependency overriding.
    *   **Split Decision:** Kept as single fixture. (Completed)

2.  **Update Test Strategies for Lifespan/`TestClient`:** (Completed for `tests/test_main.py` and initial tests in `tests/proxy/test_server.py`)
    *   **Action:** For tests using `TestClient` needing full mock setup:
        *   **Primary Mocking Point:** Patch `luthien_control.main._initialize_app_dependencies` to return `mock_container`.
        *   **Method:** Instantiate `TestClient` locally within the test *after* the patch is active.
    *   **Benefit:** Simplified test setup, correct mock application timing.

3.  **Review `db_session_fixture` and Environment Loading in `tests/conftest.py`:** (Completed)
    *   **Action:** Analyzed interaction; `db_session_fixture` now relies on pre-set admin env vars. (Completed)
    *   **Goal:** Clearer environment configuration.

4.  **Adapt Unit Tests:** (Pending)
    *   **Action:** Ensure unit tests for services/components not needing full app context avoid `TestClient` and implicit global mocks.
    *   **Strategy:** Direct instantiation with specific mock dependencies.

## Phase 3: Update Existing Tests (In Progress)

1.  **`tests/test_main.py`:** (Completed)
    *   **Action:** Refactored lifespan tests (e.g., `test_lifespan_success_path`) using the new `_initialize_app_dependencies` patching strategy. (Completed)
    *   **Cleanup:** Removed redundant individual mocks. (Completed)

2.  **Other Integration Tests:** (Next - can be combined with Phase 2.4 review)
    *   **Action:** Review other `TestClient` tests; apply new patching strategy or explicit `override_app_dependencies` fixture.

## Phase 4: Verification and Coverage Check (Pending)

1.  **Run All Tests:** Ensure all tests pass.
2.  **Analyze Test Coverage:** Assess improvements.
3.  **Review and Refine:** Make further adjustments as needed.

## Key Considerations During Implementation:

*   **Incremental Changes:** Apply changes step-by-step, testing frequently.
*   **Clarity:** Prioritize understandable test setups.
*   **`edit_verification_protocol`:** Adhere strictly.
*   **Simplicity:** Aim for the simplest effective solution.
*   **Hold Off On Proposing Solutions (for complex logic):** Debug effectively.