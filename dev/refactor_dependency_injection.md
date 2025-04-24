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
    *   Modify `get_http_client` and `get_async_db` (or its underlying factory) to potentially use the container or simplify. **Create `get_db_session` dependency if it doesn't exist, using the container's factory to yield a request-scoped session.**
    *   Modify `get_main_control_policy`:
        *   Change its dependencies to `container: DependencyContainer = Depends(get_container)`.
        *   Access `settings`, `http_client`, and `session` (via `container.db_session_factory`) from the `container` instance **for loading the policy configuration only**. Adapt the session handling logic (e.g., using `async with container.db_session_factory() as session:`). **This function loads and returns the configured policy *instance*. Dependencies required by the `apply` method (`context`, `container`, `session`) will be resolved separately at the invocation site (e.g., API endpoint) and passed during the `apply` call.**

11. **Refactor Core Logic (`db/control_policy_crud.py`) and Policy Signatures:**
    *   Modify `load_policy_from_db`:
        *   Change its signature to accept `container: DependencyContainer` instead of individual dependencies (`settings`, `http_client`, `session`).
        *   Access the required dependencies (settings, client, session factory) from the `container` instance.
        *   Adapt session usage (e.g., `async with container.db_session_factory() as session:`).
        *   If API key lookup is needed within this function, use the obtained `session` to call `get_api_key_by_value` directly (already done in Phase 1, but verify).
    *   **Refactor Policy `apply` Signatures:**
        *   Modify `ClientApiKeyAuthPolicy.apply` signature to: `async def apply(self, context: dict, container: DependencyContainer, session: AsyncSession) -> ControlPolicyResult:`. Update implementation to use these parameters.
        *   Modify `CompoundPolicy.apply` signature to: `async def apply(self, context: dict, container: DependencyContainer, session: AsyncSession) -> ControlPolicyResult:`. Update implementation to iterate sub-policies and call their `apply` methods, passing through `context`, `container`, and `session`.

11.5. **Update Base Policy Class:**
    *   **File:** `luthien_control/control_policy/control_policy.py`
    *   Define the `apply` method in the `ControlPolicy` abstract base class with the standard signature: `async def apply(self, context: dict, container: DependencyContainer, session: AsyncSession) -> ControlPolicyResult:`. Ensure it's marked as an abstract method (e.g., using `@abstractmethod`).

12. **Update API Route (`proxy/server.py`):**
    *   Modify the `api_proxy_endpoint` signature to include `session: AsyncSession = Depends(get_db_session)`. Ensure `get_db_session` dependency is created/available (see step 10).
    *   Ensure the endpoint retrieves the `container` via `Depends(get_container)`.
    *   Prepare the `context` dictionary (e.g., containing the `request`).
    *   Update the call to the orchestration function (e.g., `run_policy_flow`) to pass the resolved `context`, `container`, and `session`.

12.5. **Update Orchestration Function (`proxy/orchestration.py`):**
    *   Modify the signature of the function that calls `policy.apply` (e.g., `run_policy_flow`) to accept `context: dict`, `container: DependencyContainer`, and `session: AsyncSession` as parameters.
    *   Update the call site within this function to `await main_policy.apply(context=context, container=container, session=session)`.

13. **Refactor Tests (`tests/`):**
    *   Update test fixtures (`conftest.py`) to create mock `DependencyContainer` instances.
    *   Modify test client setups to override the `get_container` and `get_db_session` dependencies. Remove overrides for individual dependencies like `get_settings`, `get_http_client`, etc.
    *   Adjust tests that previously used `get_async_db` or `get_http_client` dependencies if their access method changes.
    *   **Ensure tests for `apply` methods directly provide mocked `context`, `container`, and `session`. Update endpoint/integration tests to verify the injection of the `session` dependency and its propagation to the `apply` method.**

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