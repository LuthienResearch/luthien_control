# Luthien Control

An intelligent proxy server for OpenAI-compatible API endpoints.

## Core Goal
To build an AI Control System (`luthien_control`) acting as an intelligent proxy server for OpenAI-compatible API endpoints. The system will intercept client requests and backend responses, apply user-defined control policies, log traffic, and eventually provide analysis tools for this data.

## Technology Stack
*   **Language:** Python (3.11+)
*   **Package Management:** Poetry
*   **Web Framework:** FastAPI
*   **Database:** PostgreSQL (using `asyncpg`)
*   **Linting/Formatting:** Ruff
*   **Security Scanning:** Bandit
*   **Testing:** Pytest, `pytest-cov` (aiming for near 100% unit test coverage)
*   **Deployment (Dev):** Fly.io

## Development Process

### Setup
1.  Clone the repository.
2.  Ensure you have Python 3.11+ and Poetry installed.
3.  Navigate to the project root directory.
4.  Install dependencies: `poetry install`

### Running Tests
*   Run unit tests: `poetry run pytest`
*   Run tests with coverage: `poetry run pytest --cov=luthien_control`

### Basic Workflow
*   Development follows a test-driven approach. See `.cursor/rules/development_workflow.mdc` for details.
*   Track progress using files in the `dev/` directory, updated per logical unit of work. See `.cursor/rules/dev_tracking.mdc`.
*   Use conventional commit messages (see `.cursor/rules/git_commit_strategy.mdc`).
*   Keep code simple and focused.

### Directory Structure
*   `luthien_control/`: Main package code (submodules: `proxy/`, `policies/`, `logging/`, `utils/`).
*   `tests/`: Top-level test directory mirroring `luthien_control`.
*   `dev/`: Development tracking files (`ProjectPlan.md`, `current_context.md`, `development_log.md`, `ToDo.md`).
*   `dev/scripts/`: Helper scripts (e.g., log rotation).
*   `.cursor/rules/`: AI assistant guidelines.
