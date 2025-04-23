# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.

- [ ] Rework `dev/ProjectPlan.md`:
  - Reorganize sections based on current status and near-term goals (e.g., Testing Framework, Pipeline Refactor).
  - Clarify distinction between major phases and specific tasks.

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

- [ ] Resolve pytest warning
- [ ] Make sure all policy serialization/deserialization methods are being tested
- [ ] Full e2e production demo
- [ ] Backfill devlog based on git commits
- [ ] Alembic migrations for default policies using new policy serialization/deserialization format