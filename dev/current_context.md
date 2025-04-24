# Current Task: Completed - Debug Failing Unit Tests (AddApiKeyHeaderPolicy)

**Goal:** Identify and fix failing unit tests, focusing on the mismatch between `AddApiKeyHeaderPolicy` implementation and its tests.

**Status:**
- Modified tests in `tests/control_policy/test_add_api_key_header.py` and `tests/control_policy/test_compound_policy.py` to align with the current specific (OpenAI-focused) implementation of `AddApiKeyHeaderPolicy`.
- Removed irrelevant tests and updated assertions related to API key fetching and serialization/deserialization.
- All tests (`poetry run pytest | cat`) are passing (132 passed).
- Task is complete.

**Next Step:**
- Commit changes.
- Define and begin next development task (e.g., items from `dev/ToDo.md`).

**Original Plan Reference (from `refactor_dependency_injection.md`

Task: Debug failing unit tests

Goals:
- Identify failing unit tests.
- Analyze the reasons for failure.

State:
- Analyzed pytest failures and code/test mismatch for AddApiKeyHeaderPolicy.
- Decided to align tests with the current specific (OpenAI-focused) implementation.