# Current Development Context

**Task:** Refactor to Dependency Injection Container

**Goal:** Replace the current ad-hoc dependency passing mechanism with a centralized `DependencyContainer` managed via FastAPI's application state and lifespan events. This aims to improve code structure, maintainability, and testability.

**Status:** Starting task. Plan created in `dev/refactor_dependency_injection.md`.

**Next Step:** Implement Step 1: Define the `DependencyContainer` class in `luthien_control/dependency_container.py`.
