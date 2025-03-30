# Luthien Control

An intelligent proxy server for OpenAI-compatible API endpoints.

## Core Goal
To build an AI Control System (`luthien_control`) acting as an intelligent proxy server for OpenAI-compatible API endpoints. The system will intercept client requests and backend responses, apply user-defined control policies, log traffic, and eventually provide analysis tools for this data.

## Technology Stack
*   **Language:** Python (3.11+)
*   **Package Management:** Poetry
*   **Web Framework:** FastAPI
*   **Server:** Uvicorn
*   **Database:** PostgreSQL (using `asyncpg`)
*   **HTTP Client:** HTTPX
*   **Configuration:** Pydantic-Settings
*   **Linting/Formatting:** Ruff
*   **Security Scanning:** Bandit
*   **Testing:** Pytest, `pytest-cov` (aiming for near 100% unit test coverage)
*   **Local DB:** Docker Compose

## Getting Started

### Prerequisites
*   Python 3.11+
*   Poetry
*   Docker and Docker Compose (for local database)

### Setup
1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd luthien_control
    ```
2.  **Install dependencies:**
    ```bash
    poetry install
    ```
3.  **Database Setup (Local Development):**
    This project uses PostgreSQL for logging. A `docker-compose.yml` file is provided for easy local setup.
    ```bash
    docker-compose up -d
    ```
    This will start a PostgreSQL container in the background.

4.  **Configuration:**
    Configuration is managed via environment variables, loaded using Pydantic-Settings. For local development, create a `.env` file in the project root.
    *   Copy the example file: `cp .env.example .env`
    *   Edit the `.env` file and provide the necessary values.
    *   **Required Variables:**
        *   `DATABASE_URL`: Connection string for the PostgreSQL database (e.g., `postgresql+asyncpg://user:password@host:port/dbname`). The default in `docker-compose.yml` and `.env.example` is `postgresql+asyncpg://luthien:secret@localhost:5432/luthien_log_db`.
        *   `TARGET_BACKEND_URL`: The URL of the backend OpenAI-compatible API you want to proxy requests to.
    *   Refer to `.cursor/rules/config_and_secrets.mdc` for more details on configuration management.

## Usage

### Running the Server
Ensure your `.env` file is configured correctly. Run the FastAPI application using Uvicorn:
```bash
poetry run uvicorn luthien_control.main:app --reload
```
The `--reload` flag enables auto-reloading when code changes are detected, useful during development.

### Logging
The proxy logs detailed information about each request and response transaction to the PostgreSQL database. This includes:
*   Timestamp of the request
*   Client IP address
*   HTTP method and path
*   Request headers and body (potentially redacted/truncated based on future policies)
*   Backend response status code
*   Response headers and body (potentially redacted/truncated based on future policies)
*   Timing information

## Development Practices

### Testing
*   Run unit tests: `poetry run pytest`
*   Run integration tests: `poetry run pytest -m integration`
*   Run all tests with coverage: `poetry run pytest --cov=luthien_control`

### Linting & Formatting
This project uses Ruff for linting and formatting.
*   Check formatting and linting: `poetry run ruff check .`
*   Apply formatting: `poetry run ruff format .`

### Security Scanning
Bandit is used to check for common security vulnerabilities.
*   Run Bandit: `poetry run bandit -r luthien_control/`

### Workflow & Tracking
*   Development follows a test-driven approach. See `.cursor/rules/development_workflow.mdc`.
*   Track progress using files in the `dev/` directory. See `.cursor/rules/dev_tracking.mdc`.
*   Use conventional commit messages. See `.cursor/rules/git_commit_strategy.mdc`.
*   Keep code simple and focused.

### Directory Structure
*   `luthien_control/`: Main package code (submodules: `proxy/`, `db/`, `config/`, `logging/`, etc.).
*   `tests/`: Top-level test directory mirroring `luthien_control`.
*   `dev/`: Development tracking files (`ProjectPlan.md`, `current_context.md`, `development_log.md`, `ToDo.md`).
*   `dev/scripts/`: Helper scripts (e.g., log rotation).
*   `.cursor/rules/`: AI assistant guidelines.
*   `docker-compose.yml`: Configuration for local development database.
*   `.env.example`: Example environment variable file.
*   `pyproject.toml`: Project metadata and dependencies (Poetry).
