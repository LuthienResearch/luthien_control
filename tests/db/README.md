# Test Directory: `tests/db`

This directory contains tests related to database interactions, model definitions, and CRUD operations using SQLModel and SQLAlchemy's async features.

## `test_sqlmodel_crud.py`

Tests the core asynchronous CRUD (Create, Read, Update, Delete - although delete isn't explicitly tested here) functions defined in `luthien_control.db.sqlmodel_crud` using an in-memory SQLite database.

*   `async_engine` (fixture): Creates a new async SQLite engine (in-memory) and manages table creation/deletion for each test.
*   `async_session` (fixture): Provides an `AsyncSession` connected to the test engine for each test.
*   `test_create_and_get_api_key`: Tests creating a `ClientApiKey` and retrieving it by value.
*   `test_list_api_keys`: Tests listing `ClientApiKey`s, including filtering by active status.
*   `test_update_api_key`: Tests updating fields of an existing `ClientApiKey`.
*   `test_update_api_key_not_found`: Tests attempting to update a non-existent `ClientApiKey`.
*   `test_get_api_key_by_value_not_found`: Tests fetching a `ClientApiKey` that doesn't exist.
*   `test_create_and_get_policy`: Tests creating a `Policy` and retrieving it by name.
*   `test_list_policies`: Tests listing `Policy` records, including filtering by active status.
*   `test_update_policy`: Tests updating fields of an existing `Policy`.
*   `test_update_policy_not_found`: Tests attempting to update a non-existent `Policy`.
*   `test_get_policy_by_name_not_found`: Tests fetching a `Policy` that doesn't exist (or is inactive).
*   `test_create_policy_duplicate_name`: Tests handling of duplicate policy name creation (relies on DB constraints/error handling).

## `test_policy_loading.py`

Tests the `load_policy_from_db` function from `luthien_control.db.sqlmodel_crud`, which handles fetching policy configuration from the database and instantiating the corresponding policy class.

*   `load_db_mock_settings` (fixture): Provides a mock `Settings` object.
*   `load_db_mock_http_client` (fixture): Provides a mock `httpx.AsyncClient`.
*   `load_db_mock_api_key_lookup` (fixture): Provides a mock `ApiKeyLookupFunc`.
*   `load_db_dependencies` (fixture): Bundles the mock dependencies.
*   `create_mock_policy_model` (helper): Creates mock `Policy` model instances for testing.
*   `test_load_policy_from_db_success`: Tests successfully loading and instantiating a policy using mocked DB fetch and instantiation.
*   `test_load_policy_from_db_not_found_patch_get`: Tests `PolicyLoadError` when the mocked `get_policy_by_name` returns `None`.
*   `test_load_policy_from_db_not_found_real_session`: Tests `PolicyLoadError` using a real session where the policy doesn't exist.
*   `test_load_policy_from_db_instantiation_fails`: Tests `PolicyLoadError` when the mocked `instantiate_policy` raises an error, using a real session.
*   `test_load_policy_from_db_missing_class_path`: Tests `PolicyLoadError` when the fetched `Policy` config lacks a class path, using a real session.

## `test_sqlmodel_integration.py`

Provides integration tests for API endpoints that interact with the SQLModel database layer. It sets up a test FastAPI application with dependency injection for the database session.

*   `async_engine` (fixture): Creates an async SQLite engine and manages tables for integration tests.
*   `async_session_factory` (fixture): Creates a session factory for the test engine.
*   `async_session` (fixture): Provides an `AsyncSession` from the factory for each test.
*   `test_app` (fixture): Creates a test FastAPI application instance with database dependency injection.
*   `get_test_db` (dependency): An async dependency within `test_app` to provide a database session to routes.
*   `create_policy_route` (route): A test FastAPI route (`POST /policies/`) for creating policies.
*   `get_policy_route` (route): A test FastAPI route (`GET /policies/{name}`) for retrieving policies.
*   `test_client` (fixture): Provides a `TestClient` for interacting with the test FastAPI app.
*   `test_create_and_get_policy`: Tests creating a policy via the API and then retrieving it.
*   `test_get_nonexistent_policy`: Tests the API response when requesting a policy that does not exist.

## `test_database_async.py`

Tests the asynchronous database setup functions in `luthien_control.db.database_async`.

*   `test_get_main_db_url_with_database_url`: Tests `_get_main_db_url` when the `DATABASE_URL` environment variable is set.
*   `test_get_main_db_url_with_postgres_vars`: Tests `_get_main_db_url` using individual `DB_*` environment variables.
*   `test_get_main_db_url_missing_vars`: Tests `_get_main_db_url` returns `None` when required variables are missing.
*   `test_get_log_db_url`: Tests `_get_log_db_url` using individual `LOG_DB_*` environment variables.
*   `test_get_log_db_url_missing_vars`: Tests `_get_log_db_url` returns `None` when required variables are missing.
*   `test_create_main_db_engine`: Tests the successful creation of the main database engine using mocks.
*   `test_create_main_db_engine_url_error`: Tests engine creation failure when the database URL cannot be determined.
*   `test_get_main_db_session_error`: Tests that `get_main_db_session` raises a `RuntimeError` if the engine is not initialized.

## `test_models.py`

Contains basic tests for the SQLModel model definitions in `luthien_control.db.sqlmodel_models`.

*   `test_policy_creation`: Tests successful creation of a `Policy` model, verifying default values and timestamp generation.
*   `test_policy_creation_with_timestamps`: Tests successful creation of a `Policy` model with explicitly provided timestamps and other fields.

## `mock_policies.py`

Contains various mock `ControlPolicy` implementations used for testing policy loading and instantiation logic.

*   `MockSimplePolicy`: A basic mock policy accepting standard dependencies (settings, http_client) and a timeout.
*   `MockNestedPolicy`: A mock policy that contains another `ControlPolicy` instance.
*   `MockListPolicy`: A mock policy that accepts a list of policies (or other items) and a mode string.
*   `MockPolicyWithApiKeyLookup`: A mock policy demonstrating injection of the `ApiKeyLookupFunc` dependency.
*   `MockNoArgsPolicy`: A mock policy with an empty `__init__` signature.
*   `MockMissingArgPolicy`: A mock policy intentionally missing standard dependencies to test injection failure.
*   `MockCompoundPolicy`: A mock policy inheriting from `CompoundPolicy` to test instantiation with a list of sub-policies.

## `conftest.py`

Contains shared fixtures for the `tests/db` directory, primarily for setting up the asynchronous test database environment (`async_engine`, `async_session`, `mock_db_session`). 