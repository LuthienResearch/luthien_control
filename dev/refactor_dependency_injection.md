# Plan: Refactor Dependencies (Prerequisites & DI Container)

**Goal:** Refactor dependency management, first by removing unnecessary direct dependencies (`api_key_lookup`, `response_builder`), then by implementing a centralized Dependency Injection Container for remaining core services.

**Phase 1: Prerequisite Refactoring (Remove Direct Dependencies)**

1.  **Refactor `ClientApiKeyAuthPolicy` to use Session:**
    *   **File:** `luthien_control/control_policy/client_api_key_auth.py`
    *   Remove `"api_key_lookup"` from `REQUIRED_DEPENDENCIES`.
    *   Remove `api_key_lookup` parameter from `__init__`.
    *   Modify `from_serialized`: Remove `api_key_lookup` handling from `kwargs` and the `cls()` call.
    *   Modify `apply`: Replace `await self._api_key_lookup(session, ...)` with `await get_api_key_by_value(session, ...)`. Ensure `get_api_key_by_value` is imported.
2.  **Refactor `CompoundPolicy` to remove `api_key_lookup` handling:**
    *   **File:** `luthien_control/control_policy/compound_policy.py`
    *   Remove `"api_key_lookup"` from `REQUIRED_DEPENDENCIES`.
    *   Review `__init__` and `from_serialized` to remove `api_key_lookup` from `kwargs` processing/passing.
3.  **Update Policy Loading Logic:**
    *   **File:** `luthien_control/db/control_policy_crud.py` (`load_policy_from_db`)
        *   Remove `api_key_lookup` from `kwargs` passed to `load_policy`.
    *   **File:** `luthien_control/dependencies.py` (`get_main_control_policy`)
        *   Remove `api_key_lookup_func` variable.
        *   Remove `api_key_lookup` parameter from the `load_policy_from_db` call.
        *   Update docstring.
4.  **Remove `get_response_builder` Dependency:**
    *   **File:** `luthien_control/dependencies.py`
        *   Delete the `get_response_builder` function.
    *   **File:** `luthien_control/proxy/server.py` (API Endpoint)
        *   Remove the `builder: ResponseBuilder = Depends(get_response_builder)` dependency.
        *   Instantiate `DefaultResponseBuilder()` directly where needed.
5.  **Refactor Tests for Prerequisite Changes:**
    *   Update tests for `ClientApiKeyAuthPolicy`, `CompoundPolicy`, `load_policy_from_db`, `get_main_control_policy` to remove mocking/injection of `api_key_lookup`.
    *   Ensure `ClientApiKeyAuthPolicy` tests mock the session and potentially patch `get_api_key_by_value`.
    *   Remove tests specifically for `get_response_builder` (`tests/test_dependencies.py`).
    *   Update tests for the `proxy/server.py` endpoint to reflect the removal of the `response_builder` dependency.
6.  **Test Phase 1:**
    *   Run `poetry run pytest | cat` and fix any failures.
    *   Run `poetry run bandit -r luthien_control/ | cat`.

**Phase 2: Implement Dependency Injection Container**

7.  **Define Container:** Create `luthien_control/dependency_container.py` with a `DependencyContainer` class holding attributes/factories for core shared services:
    *   `settings: Settings`
    *   `http_client: httpx.AsyncClient`
    *   `db_session_factory: Callable[[], AsyncContextManager[AsyncSession]]` (e.g., the `get_db_session` function)

8.  **Integrate into Lifespan (`main.py`):**
    *   Modify the FastAPI application's lifespan manager.
    *   On startup:
        *   Import necessary components (`DependencyContainer`, `Settings`, `httpx`, `get_db_session`).
        *   Create the `httpx.AsyncClient`.
        *   Instantiate `DependencyContainer` with the real dependencies/factories.
        *   Store the container instance in `app.state['container']`.
    *   On shutdown:
        *   Retrieve the container and client from `app.state`.
        *   Close the `httpx.AsyncClient`.

9.  **Create Container Dependency (`dependencies.py`):**
    *   Add `get_container(request: Request) -> DependencyContainer` function to retrieve the container from `request.app.state['container']`. Include error handling if not found.

10. **Refactor Dependency Providers (`dependencies.py`):**
    *   Modify `get_http_client` and `get_async_db` (or its underlying factory) to potentially use the container or simplify.
    *   Modify `get_main_control_policy`:
        *   Change its dependencies to `container: DependencyContainer = Depends(get_container)`.
        *   Access `settings`, `http_client`, and `session` (via `container.db_session_factory`) from the `container` instance. Adapt the session handling logic (e.g., using `async with container.db_session_factory() as session:`).

11. **Refactor Core Logic (`db/control_policy_crud.py`):**
    *   Modify `load_policy_from_db`:
        *   Change its signature to accept `container: DependencyContainer` instead of individual dependencies (`settings`, `http_client`, `session`).
        *   Access the required dependencies (settings, client, session factory) from the `container` instance.
        *   Adapt session usage (e.g., `async with container.db_session_factory() as session:`).
        *   If API key lookup is needed within this function, use the obtained `session` to call `get_api_key_by_value` directly (already done in Phase 1, but verify).
    *   **Refactor `ClientApiKeyAuthPolicy` (`luthien_control/control_policy/client_api_key_auth.py`):**
        *   Modify `apply` to accept an `AsyncSession` as a parameter instead of creating its own using `get_db_session()`.
        *   Ensure the policy loading mechanism (likely within `load_policy_from_db` or a related function modified in this phase) provides the session from the container's session factory when instantiating/calling `ClientApiKeyAuthPolicy`.

12. **Verify API Routes (`proxy/server.py`):**
    *   Review endpoint dependencies (e.g., `Depends(get_main_control_policy)`). Should require no changes due to this phase, but verify.

13. **Refactor Tests (`tests/`):**
    *   Update test fixtures (`conftest.py`) to create mock `DependencyContainer` instances.
    *   Modify test client setups to override the single `get_container` dependency. Remove overrides for individual dependencies like `get_settings`, `get_http_client`, etc.
    *   Adjust tests that previously used `get_async_db` or `get_http_client` dependencies if their access method changes.

14. **Test Phase 2:**
    *   Run `poetry run pytest | cat` and fix any failures.
    *   Run `poetry run bandit -r luthien_control/ | cat`.

15. **Final Documentation & Tracking:**
    *   Ensure docstrings are updated where signatures or behavior changed.
    *   Perform the mandatory development tracking update (`rotate_dev_log.sh`, `development_log.md`, `current_context.md`).

**Potential Downsides/Considerations (Applies mainly to Phase 2):**

*   **Initial Boilerplate:** Requires setting up the `DependencyContainer` class, lifespan integration, and `get_container` dependency.
*   **"God Object" Risk:** The container could potentially become overly large if not carefully managed, hiding specific component dependencies. Keep it focused on core services.
*   **Indirection:** Specific dependencies aren't visible in function signatures (`Depends(get_container)`), requiring inspection of the function body.
*   **Overkill for Simple Cases:** May add unnecessary complexity for applications with very few shared dependencies (though likely justified here).
*   **Testing Complexity:** Creating mock containers could become complex if the container's own initialization logic is overly intricate. Keep container setup simple. 