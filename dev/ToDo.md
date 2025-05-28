# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.

- [ ] Rework `dev/ProjectPlan.md`:
  - Reorganize sections based on current status and near-term goals (e.g., Testing Framework, Pipeline Refactor).
  - Clarify distinction between major phases and specific tasks.

## Code Quality and Architecture

- [ ] **Error Handling Standardization**
  - Create consistent error handling strategy document
  - Audit `client_api_key_crud.py` and other modules that return `None` on errors
  - Update CRUD operations to either always return Optional types or always raise exceptions
  - Add robust error type hierarchy for all expected failure modes

- [ ] **Simplify Serialization**
  - Create base class helper methods for common serialization patterns
  - Implement serialization validation at the base class level
  - Remove duplicate validation logic in `from_serialized` methods
  - Add proper type safety for serialization/deserialization

- [ ] **Transaction Context Refinement**
  - Document clear ownership of TransactionContext fields
  - Split TransactionContext into smaller, purpose-specific objects
  - Add validation to prevent unexpected modifications
  - Consider immutable context pattern with transforms

- [ ] **Type Safety Improvements**
  - Remove manual `cast()` usage where possible
  - Add proper type guards instead of isinstance checks
  - Use more specific types instead of Any/Dict
  - Add runtime type validation at API boundaries

- [ ] **Code Simplification**
  - Audit the conditions system for excessive complexity
  - Create simplified interfaces for common condition patterns
  - Refactor complex database interaction patterns
  - Break up long methods with too many responsibilities

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

- [ ] **Investigate Policy Loading Performance:** Profile/analyze frequency and duration of `load_policy_from_db` calls to determine if DB/instantiation overhead is significant.
- [ ] **Design Policy Caching Strategy:** If performance analysis indicates a need, design a caching mechanism (key strategy, storage, TTL, invalidation) for loaded `ControlPolicy` instances.
- [ ] **Implement Policy Caching (If Designed):** Build the caching layer decided upon in the previous step, potentially integrating with `DependencyContainer`.
- [ ] **Determine Optimal `ResponseBuilder` Lifecycle:** Decide if `DefaultResponseBuilder` is stateless (singleton) or needs per-request instantiation. Update `DependencyContainer` setup accordingly.

- [ ] Implement package-wide logging system
- [ ] Inconsistent use of 'db'/'postgres' in variable naming/docs

## Testing Improvements

- [ ] **Test Refactoring**
  - Create reusable database mocking fixtures in a central location
  - Reduce deep mocking by creating better test-friendly interfaces
  - Fix skipped test for async context manager in `test_database_async.py`
  - Create helper functions for common test setup patterns

- [ ] **Review and Simplify Tests - Remove Unnecessary Mocking:**
  - **Goal:** Apply test writing guidelines consistently across the codebase to eliminate over-mocking.
  - **Status:** ✅ Completed for `tests/control_policy/tx_logging/` (removed ~135 lines of mock infrastructure)
  - **Remaining areas to review:**
    - `tests/control_policy/` - Check for complex mock factories and unnecessary mocking
    - `tests/proxy/` - Review proxy-related tests for over-mocking  
    - `tests/core/` - Ensure core functionality tests use real objects where appropriate
  - **Guidelines:** Default to real objects, only mock external dependencies (network, file I/O, databases, time), avoid mock factories for simple data objects
  - **Benefits:** Cleaner code, better test coverage, easier maintenance, clearer test intent

- [ ] **Testing Coverage Gaps**
  - Add tests for `control_policy.py` (currently 82%)
  - Improve coverage of `send_backend_request.py` (currently 80%)
  - Add tests for `serial_policy.py` (currently 88%)
  - Complete tests for `client_api_key_auth.py` (currently 91%)
  - Make sure all policy serialization/deserialization methods are being tested

## DevOps and Infrastructure

- [ ] security scan automation
- [ ] typehintchecking automation
- [ ] ruff automation
- [ ] Full e2e production demo
- [ ] Backfill devlog based on git commits
- [ ] Alembic migrations for default policies using new policy serialization/deserialization format

## Data Management

- [ ] Migrate all datetime columns to use `TIMESTAMP WITH TIME ZONE` instead of the current `TIMESTAMP WITHOUT TIME ZONE`
  - All models would use true timezone-aware datetimes without stripping tzinfo
  - More robust for handling timezone-related edge cases and DST transitions
  - Requires careful migration to avoid breaking existing data and queries

## Completed Items

- [X] client api check as policy (instead of in core)
- [X] Fix database session handling in policies
  - Policies should not rely on a context.session attribute that isn't defined in TransactionContext
  - Instead, use get_main_db_session() directly in policy methods that need database access
  - Updated tests to properly mock database session access
  - Ensures CompoundPolicy can correctly instantiate member policies
- [X] Eliminate all traces of CONTROL_POLICIES
- [X] Eliminate remaining log db cruft
- [X] Eliminate redundancy and overabstraction in db connection management
- [X] Resolve pytest warning
- [X] Policy crud aligns with new serialization approach
- [X] Archived devlogs should not be compressed