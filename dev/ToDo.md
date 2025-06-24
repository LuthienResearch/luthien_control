# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.


## Code Quality and Architecture

- [ ] **Error Handling Standardization**
  - Create consistent error handling strategy document
  - Audit `client_api_key_crud.py` and other modules that return `None` on errors
  - Update CRUD operations to either always return Optional types or always raise exceptions
  - Add robust error type hierarchy for all expected failure modes

- [ ] Inconsistent use of 'db'/'postgres' in variable naming/docs

## Testing Improvements

- [ ] **Review and Simplify Tests - Remove Unnecessary Mocking:**
  - **Goal:** Apply test writing guidelines consistently across the codebase to eliminate over-mocking.
  - **Status:** ✅ Completed for `tests/control_policy/tx_logging/` (removed ~135 lines of mock infrastructure)
  - **Remaining areas to review:**
    - `tests/control_policy/` - Check for complex mock factories and unnecessary mocking
    - `tests/proxy/` - Review proxy-related tests for over-mocking  
    - `tests/core/` - Ensure core functionality tests use real objects where appropriate
  - **Guidelines:** Default to real objects, only mock external dependencies (network, file I/O, databases, time), avoid mock factories for simple data objects

## Misc
- [ ] Add an AsyncSession factory to DependencyContainer and remove as a separate arg for control_policy.apply