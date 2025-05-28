# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.

- [ ] Rework `dev/ProjectPlan.md`:
  - Reorganize sections based on current status and near-term goals (e.g., Testing Framework, Pipeline Refactor).
  - Clarify distinction between major phases and specific tasks.

- [ ] **Review and Simplify Tests - Remove Unnecessary Mocking:**
  - **Goal:** Apply test writing guidelines consistently across the codebase to eliminate over-mocking.
  - **Status:** ✅ Completed for `tests/control_policy/tx_logging/` (removed ~135 lines of mock infrastructure)
  - **Remaining areas to review:**
    - `tests/control_policy/` - Check for complex mock factories and unnecessary mocking
    - `tests/proxy/` - Review proxy-related tests for over-mocking  
    - `tests/core/` - Ensure core functionality tests use real objects where appropriate
  - **Guidelines:** Default to real objects, only mock external dependencies (network, file I/O, databases, time), avoid mock factories for simple data objects
  - **Benefits:** Cleaner code, better test coverage, easier maintenance, clearer test intent

- [ ] Implement package-wide logging system

- [ ] security scan automation
- [ ] typehintchecking automation
- [ ] ruff automation
- [X] client api check as policy (instead of in core)

- [ ] Migrate all datetime columns to use `TIMESTAMP WITH TIME ZONE` instead of the current `TIMESTAMP WITHOUT TIME ZONE`
  - All models would use true timezone-aware datetimes without stripping tzinfo
  - More robust for handling timezone-related edge cases and DST transitions
  - Requires careful migration to avoid breaking existing data and queries

- [X] Fix database session handling in policies
  - Policies should not rely on a context.session attribute that isn't defined in TransactionContext
  - Instead, use get_main_db_session() directly in policy methods that need database access
  - Updated tests to properly mock database session access
  - Ensures CompoundPolicy can correctly instantiate member policies

- [X] Eliminate all traces of CONTROL_POLICIES
- [X] Eliminate remaining log db cruft
- [X] Eliminate redundancy and overabstraction in db connection management

- [ ] **Refactor `SendBackendRequestPolicy`:**
  - **Goal:** Split into `PrepareBackendRequestPolicy` and `ExecuteBackendRequestPolicy`.
  - **Reason:** Improve Separation of Concerns (SRP), testability, and flexibility.
  - **Details:**
    - `PrepareBackendRequestPolicy`: Handles URL construction, header preparation (copying, excluding, setting Host/Auth/Accept-Encoding), reads original body (if needed), creates a *new* backend `httpx.Request` object. Stores result in `context.backend_request` (new `TransactionContext` attribute).
    - `ExecuteBackendRequestPolicy`: Takes `context.backend_request`, uses injected `http_client` to send it, stores `httpx.Response` in `context.backend_response` (new `TransactionContext` attribute). Handles network errors.
    - Update `TransactionContext` with `backend_request: httpx.Request | None = None` and `backend_response: httpx.Response | None = None`.
    - Remove old `SendBackendRequestPolicy` and its tests.
    - Update policy chain configurations.
  - **Origin:** Identified during review of `tests/control_policy/test_send_backend_request.py` due to test length and policy complexity.

- [X] Resolve pytest warning
- [ ] Make sure all policy serialization/deserialization methods are being tested
- [ ] Full e2e production demo
- [ ] Backfill devlog based on git commits
- [X] Policy crud aligns with new serialization approach
- [ ] Alembic migrations for default policies using new policy serialization/deserialization format
- [X] Archived devlogs should not be compressed

- [ ] **Investigate Policy Loading Performance:** Profile/analyze frequency and duration of `load_policy_from_db` calls to determine if DB/instantiation overhead is significant.
- [ ] **Design Policy Caching Strategy:** If performance analysis indicates a need, design a caching mechanism (key strategy, storage, TTL, invalidation) for loaded `ControlPolicy` instances.
- [ ] **Implement Policy Caching (If Designed):** Build the caching layer decided upon in the previous step, potentially integrating with `DependencyContainer`.
- [ ] **Determine Optimal `ResponseBuilder` Lifecycle:** Decide if `DefaultResponseBuilder` is stateless (singleton) or needs per-request instantiation. Update `DependencyContainer` setup accordingly.

## Application Logic Fixes Identified During Testing (2025-04-25)

- [X] **`luthien_control/control_policy/exceptions.py`:**
    - Review `__init__` methods of `PolicyLoadError`, `ClientAuthenticationError`, and `ClientAuthenticationNotFoundError`.
    - Ensure they correctly handle and propagate `policy_name` and `status_code` arguments to the `ControlPolicyError` base class initializer, consistent with the base class definition and expected usage in tests (e.g., `test_exceptions.py::test_policy_load_error`, `test_exceptions.py::test_client_authentication_error`). Currently, attributes like `status_code` might be overwritten or not set as expected.

- [X] **`luthien_control/control_policy/loader.py`:**
    - In `load_policy` function, after the line `policy_class = POLICY_NAME_TO_CLASS.get(policy_type)`, add a check: `if policy_class is None:`.
    - If it is `None`, raise `PolicyLoadError(f"Unknown policy type: '{policy_type}'. ...")` immediately.
    - Currently, the code proceeds with `policy_class` as `None`, leading to an `AttributeError` later, which is then wrapped in a less specific `PolicyLoadError`. This fix provides earlier and more specific error feedback (as expected by `test_loader.py::test_load_policy_unknown_type`).