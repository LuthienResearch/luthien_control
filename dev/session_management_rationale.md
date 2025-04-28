# Rationale for Session Factory in Container and Separate Session Dependency

This document explains the reasoning behind the chosen approach for managing database sessions using a `DependencyContainer` and a separate FastAPI dependency function.

**The Approach:**

1.  **`db_session_factory` in `DependencyContainer`:** The main `DependencyContainer` instance, typically created at application startup, holds a configured `async_sessionmaker` (or equivalent factory function) responsible for creating new `AsyncSession` instances. This factory encapsulates the database engine and connection configuration.
2.  **`get_db_session` FastAPI Dependency:** A separate dependency function (e.g., `async def get_db_session(container: DependencyContainer = Depends(get_container)) -> AsyncIterator[AsyncSession]: ...`) is defined. This function uses the `db_session_factory` obtained from the injected `container` to create a session, `yield` it for use within the request scope, and manage its lifecycle (commit/rollback/close) using a `try...finally` block or context manager (`async with`).

**Reasoning:**

1.  **Centralized Configuration:** Placing the `db_session_factory` in the `DependencyContainer` centralizes the database connection configuration (engine details, pool settings, etc.). This ensures consistency across the application. The container, initialized at startup, becomes the single source of truth for *how* to connect to the database.
2.  **Separation of Concerns:** This approach cleanly separates two distinct responsibilities:
    *   **Container:** Responsible for holding the *means* to create sessions (the factory).
    *   **`get_db_session` Dependency:** Responsible for the *lifecycle management* of a single session within the context of a single request. It leverages FastAPI's `Depends` mechanism to create a session, make it available, and ensure proper transaction handling (commit/rollback) based on the request's success or failure.
3.  **Leveraging FastAPI Idioms:** Using a dedicated `Depends` function for the session (`get_db_session`) aligns with standard FastAPI patterns for managing request-scoped resources. FastAPI automatically handles the caching of the yielded session, ensuring that all dependencies within the same request receive the *identical* session instance, which is crucial for transactional integrity.
4.  **Transactional Integrity:** By having `get_db_session` manage the transaction (`yield` within a context manager or try/finally), we guarantee that all operations using the session within a single request are part of the same database transaction. This avoids the issues of partial commits that would arise if each component created its own session from the factory.
5.  **Flexibility and Future Use:** While request handlers are the primary consumers via `Depends(get_db_session)`, keeping the `db_session_factory` accessible in the container provides flexibility:
    *   **Background Tasks/Workers:** Processes running outside the FastAPI request lifecycle can potentially access the container (or have the factory passed to them) to create sessions using the same application configuration.
    *   **CLI Tools/Scripts:** Utility scripts can use the factory for database operations.
    *   **Testing:** Direct access to the factory can be useful in specific testing scenarios.
6.  **Testability:** Mocking is straightforward. For unit tests, you can mock the `get_db_session` dependency. For integration tests needing real database interactions but potentially different configurations, you might provide a test-specific container with a test database factory.

In summary, while the `get_db_session` dependency relies on the factory within the container, keeping both serves distinct purposes, promotes clean architecture, leverages FastAPI's strengths, ensures transactional correctness, and provides future flexibility. 