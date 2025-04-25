# Luthien Control

> **⚠️ EARLY DEVELOPMENT WARNING ⚠️**
>
> This project is currently in the early stages of development. It is **not yet suitable for production use**.
> Expect frequent updates, potential bugs, and **breaking changes** to the API and functionality without prior notice.
> Use at your own risk during this phase.

Luthien Control is a framework to implement AI Control policies on OpenAI-API compatible endpoints. The Luthien Control server is a proxy server that sits between clients and the AI backend, implementing AI Control policies on traffic that goes between them.


## Technology Stack
*   **Language:** Python (3.11+)
*   **Package Management:** Poetry
*   **Web Framework:** FastAPI
*   **Server:** Uvicorn
*   **Database:** 
    * PostgreSQL (using `asyncpg`) - Legacy system
    * SQLModel (SQLAlchemy + Pydantic) with Alembic - New system (in transition)
*   **HTTP Client:** HTTPX
*   **Configuration:** Environment variables via `python-dotenv`
*   **Linting/Formatting:** Ruff
*   **Security Scanning:** Bandit
*   **Testing:** Pytest, `pytest-cov`
*   **Local DB:** Docker Compose

## Getting Started

### Prerequisites
*   Python 3.11+
*   Poetry
*   Docker and Docker Compose (for local database)

### Setup
1.  **Clone the repository:**
    ```bash
    git clone git@github.com:LuthienResearch/luthien_control.git
    cd luthien_control
    ```
2.  **Install dependencies:**
    ```bash
    poetry install
    ```
3.  **Database Setup (Local Development):**
    This project uses PostgreSQL for logging request/response data. A `docker-compose.yml` file is provided for easy local setup.
    ```bash
    docker-compose up -d
    ```
    This will start a PostgreSQL container named `luthien-db-1` in the background.

4.  **Configuration:**
    Configuration is managed via environment variables, loaded using `python-dotenv` from a `.env` file in the project root during development.
    *   Copy the example file: `cp .env.example .env`
    *   Edit the `.env` file and provide the necessary values.
    *   **Required Variables:**
        *   `BACKEND_URL`: The URL of the backend OpenAI-compatible API you want to proxy requests to (e.g., `https://api.openai.com/v1`).
    *   **Optional Variables:**
        *   `OPENAI_API_KEY`: API key for the backend service (required if the backend needs authentication, like OpenAI).
        *   `POLICY_MODULE`: Python path to the policy class to load (defaults to `luthien_control.policies.examples.no_op.NoOpPolicy`).
        *   `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME_NEW`: Database connection details for the *main* application database.
        *   `DB_NAME_NEW`: Database name for the new SQLModel database (see [SQLModel Migration](docs/sqlmodel_migration.md)).
        *   `LOG_DB_USER`, `LOG_DB_PASSWORD`, `LOG_DB_HOST`, `LOG_DB_PORT`, `LOG_DB_NAME`: Database connection details for the *request/response logging* database. The defaults match the `docker-compose.yml` setup (`LOG_DB_USER=luthien`, `LOG_DB_PASSWORD=secret`, `LOG_DB_HOST=localhost`, `LOG_DB_PORT=5432`, `LOG_DB_NAME=luthien_log_db`).
        *   `LOG_DB_POOL_MIN_SIZE`, `LOG_DB_POOL_MAX_SIZE`: Optional pool size settings for the logging database connection.

## Usage

### Running the Server
Ensure your `.env` file is configured correctly. Run the FastAPI application using Uvicorn:
```bash
poetry run uvicorn luthien_control.main:app --reload
```
The `--reload` flag enables auto-reloading when code changes are detected, useful during development.

## Development Practices

### Testing
This project uses Pytest. Tests are categorized using markers defined in `pyproject.toml`:
*   **Unit Tests (`unit` marker or no marker):** Run by default (`poetry run pytest`). They typically mock external dependencies and use `.env.test` if it exists.
*   **Integration Tests (`integration` marker):** Excluded by default. These tests might interact with local services like the database defined in `docker-compose.yml` and use `.env`.
*   **End-to-End (E2E) Tests (`e2e` marker):** Excluded by default. These tests run against a live proxy server (either local or deployed) which connects to a *real backend API* (e.g., OpenAI). They require network access, `OPENAI_API_KEY` in the environment, and potentially incur API costs.

**Running Tests:**
*   **Run default tests (unit tests):**
    ```bash
    poetry run pytest
    ```
*   **Run integration tests:**
    ```bash
    poetry run pytest -m integration
    ```
*   **Run End-to-End (E2E) tests against a locally started server:**
    *Ensure `OPENAI_API_KEY` is set in your environment or `.env` file.*
    ```bash
    poetry run pytest -m e2e
    ```
*   **Run E2E tests against a deployed proxy server:**
    *Ensure `OPENAI_API_KEY` is set in your environment.*
    *(The current development deployment is on Fly.io under the app name `luthien-control`)*
    ```bash
    poetry run pytest -m e2e --e2e-target-url https://your-deployed-proxy.example.com
    ```
*   **Run all non-E2E tests (Unit & Integration) with coverage:**
    ```bash
    poetry run pytest --cov=luthien_control -m "not e2e"
    ```
*   **Run all tests (Unit, Integration & E2E) with coverage:**
    ```bash
    poetry run pytest --cov=luthien_control
    ```
    *(Note: Coverage reporting might be less meaningful for E2E tests involving separate processes.)*

**Test Configuration:**
*   Tests without the `integration` or `e2e` marker primarily use environment variables defined in `.env.test` (if it exists).
*   Integration tests use environment variables from `.env`.
*   E2E tests require the `OPENAI_API_KEY` environment variable and potentially others depending on the target backend and policies.
*   The E2E local server fixture defaults to using `https://api.openai.com/v1` as the `BACKEND_URL` unless overridden by an existing environment variable.

### Linting & Formatting
This project uses Ruff for linting and formatting.
*   Check formatting and linting: `poetry run ruff check .`
*   Apply formatting: `poetry run ruff format .`

### Security Scanning
Bandit is used to check for common security vulnerabilities.
*   Run Bandit: `poetry run bandit -r luthien_control/`

### Code Complexity Analysis
Radon is used to analyze code complexity (e.g., cyclomatic complexity). This helps identify potentially complex and hard-to-maintain code.
*   Check complexity: `poetry run radon cc luthien_control/ -a -s` (shows average and sorted results)
*   Check maintainability index: `poetry run radon mi luthien_control -s`

### Directory Structure
*   `luthien_control/`: Main package code (submodules: `proxy/`, `db/`, `config/`, `logging/`, `core/`, etc.).
*   `tests/`: Top-level test directory mirroring `luthien_control`.
*   `dev/`: Development tracking files (`ProjectPlan.md`, `current_context.md`, `development_log.md`, `ToDo.md`).
*   `docs/`: Documentation files, including migration guides.
*   `scripts/`: Helper scripts (database creation, log rotation, etc.).
*   `alembic/`: Database migration files for SQLModel.
*   `docker-compose.yml`: Configuration for local development database.
*   `.env.example`: Example environment variable file.
*   `pyproject.toml`: Project metadata and dependencies (Poetry).
*   `.cursor/rules/`: AI assistant guidelines.
