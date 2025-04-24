# Plan: Simplify Orchestration Error Handling and Testing

**Goal:** Refactor the `run_policy_flow` function in `luthien_control/proxy/orchestration.py` and its corresponding tests in `tests/proxy/test_orchestration.py` to achieve:
1.  Simpler, more predictable, and easier-to-maintain error handling logic within `run_policy_flow`.
2.  Less brittle tests that are focused on observable behavior rather than internal implementation details.

**Problem:** The current error handling in `run_policy_flow` involves nested `try...except` blocks and attempts to use the response builder even after policy errors, leading to complex control flow. The associated tests require extensive mocking of internal details, making them fragile and difficult to debug when the implementation changes.

## Phase 1: Simplify Application Logic

**Strategy:** Modify `run_policy_flow` to adopt a clearer separation between handling expected policy errors (`ControlPolicyError`) and unexpected errors (`Exception`). Eliminate the attempt to use the potentially complex `DefaultResponseBuilder` after a `ControlPolicyError`.

**Implementation Steps (`luthien_control/proxy/orchestration.py`):**

1.  **Modify `except ControlPolicyError as e:` block:**
    *   Remove the `try...except` block wrapping the call to `builder.build_response(context)`.
    *   Remove the call to `builder.build_response(context)` entirely from this block.
    *   Instead, directly create and assign `final_response` using `fastapi.responses.JSONResponse`.
    *   Extract relevant information from the `ControlPolicyError` `e` (e.g., a suggested status code if the exception provides one, error details) and the `context` (transaction ID) to populate the `JSONResponse`. Use a default status code (e.g., 400 or 500) if the exception doesn't provide one.
    *   Ensure the logger still logs the `ControlPolicyError` warning.

2.  **Review `except Exception as e:` block:**
    *   Keep the existing logic: log the unexpected exception, attempt to build a response using the `builder` within a nested `try...except`, and fall back to a generic `JSONResponse` if the builder itself fails. This handles truly unexpected scenarios during the normal flow or builder failures.

## Phase 2: Refactor Testing Approach

**Strategy:** Update tests in `tests/proxy/test_orchestration.py` to align with the simplified logic and reduce brittleness. Focus on input/output behavior.

**Implementation Steps (`tests/proxy/test_orchestration.py`):**

1.  **Review Test Fixtures:** Keep mocks for `request`, `main_policy`, `dependencies`, and `session` as these represent the primary inputs/dependencies.
2.  **Update `test_run_policy_flow_policy_exception`:**
    *   Remove mocks/patches related to `DefaultResponseBuilder` and `JSONResponse` within this specific test if they are no longer relevant to the direct `JSONResponse` creation path.
    *   Modify assertions to check:
        *   `policy.apply` was called.
        *   `logger.warning` was called with the `ControlPolicyError`.
        *   The *returned response* has the expected status code and content structure defined for the direct `JSONResponse` created in the simplified `except ControlPolicyError` block.
        *   `logger.exception` was *not* called.
        *   `DefaultResponseBuilder.build_response` was *not* called.
3.  **Update `test_run_policy_flow_unexpected_exception`:**
    *   Keep mocks for `logger`, `DefaultResponseBuilder`, and potentially `JSONResponse` as this path still involves them.
    *   Modify assertions to check:
        *   `policy.apply` was called (and raised the unexpected exception).
        *   `logger.exception` was called for the *initial* unexpected error.
        *   `DefaultResponseBuilder.build_response` was called *once* (the attempt within the `except Exception:` block).
        *   The final response matches the expected output from the *mocked* `build_response` (since the builder is mocked to succeed in this test).
4.  **Update `test_run_policy_flow_unexpected_exception_during_build`:**
    *   This test remains important for the `except Exception:` path.
    *   Keep mocks for `logger`, `DefaultResponseBuilder` (configured to raise an error on `build_response`), and `JSONResponse` (for the final fallback).
    *   Modify assertions based on the *current* logic (which should remain unchanged in this path):
        *   `policy.apply` was called (raising the initial unexpected error).
        *   `logger.exception` was called *twice* (once for the initial error `e`, once for the builder error `build_e`). Check log contents.
        *   `DefaultResponseBuilder.build_response` was called *once* (raising `build_e`).
        *   `JSONResponse` (the fallback) was called once. Check its arguments.
        *   The final response matches the fallback `JSONResponse`.
5.  **Update `test_run_policy_flow_successful`:**
    *   This test should remain largely the same, primarily patching `DefaultResponseBuilder` to verify the happy path uses the builder correctly. Reduce internal assertions if possible, focusing on the final `response`.
6.  **Remove Redundant/Brittle Assertions:** Go through all tests and remove assertions checking `call_count` or exact `call_args` for internal mocks (`logger`, `uuid`, `JSONResponse` factory) unless verifying them is *essential* to the specific goal of the test case. Focus on:
    *   Was the correct policy `apply` method called?
    *   Was the final response object correct (type, status code, content)?
    *   Were critical errors logged appropriately (e.g., `logger.exception` called when expected)?

## Phase 3: Review and Iterate

1.  **Run Tests:** Ensure all tests pass after implementing the logic and test changes.
2.  **Code Review:** Review the simplified `run_policy_flow` logic for clarity and correctness.
3.  **Test Review:** Review the refactored tests for clarity, robustness, and adequate coverage of the simplified logic.
4.  **Consider Further Simplification:** Evaluate if more simplification is possible or desirable after this phase. 