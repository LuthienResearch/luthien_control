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
    
    **Note:** Ensure Docker is running before executing the following command.
    ```bash
    cp .env.example .env
    docker compose up -d   # Note: Use 'docker-compose' if using older Docker versions
    ```
    Docker Compose will automatically use variables from your `.env` file (if it exists in the project root) to configure the PostgreSQL container. Specifically, it will look for `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `DB_PORT`. If these are not found in `.env`, the default values specified in `docker-compose.yml` will be used.

    This will start a PostgreSQL container named `luthien-control-db-1` (or similar, depending on your project name in `docker-compose.yml`) in the background.
    
    **Using a Different Container/Port:**
    If you need to run multiple instances or avoid conflicts with existing containers:
    ```bash
    # Create a custom docker-compose file
    cp docker-compose.yml docker-compose.custom.yml
    
    # Edit docker-compose.custom.yml as needed
    
    # Start your custom container
    docker compose -f docker-compose.custom.yml up -d
    
    # Don't forget to update your .env file
    ```
    
    **Apply Database Migrations:**
    After setting up the database container, apply the migrations to create the required schema:
    ```bash
    # Apply all migrations
    poetry run alembic upgrade head
    ```

4.  **Configuration:**
    Configuration is managed via environment variables, loaded using `python-dotenv` from a `.env` file in the project root during development.
    *   The example file `.env.example` includes reasonable defaults for local development that should work with the Docker setup.
    *   Edit the `.env` file if you need to customize any values.
    *   **Required Variables:**
        *   `BACKEND_URL`: The URL of the backend OpenAI-compatible API you want to proxy requests to (e.g., `https://api.openai.com/v1`).
        *   `OPENAI_API_KEY`: API key for the backend service (required if the backend needs authentication, like OpenAI).
    *   **Database Variables:**
        *   `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`: Database connection details for the main application database. The values for `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `DB_PORT` in your `.env` file are also used by `docker-compose.yml` to set up the local PostgreSQL container. The defaults in `.env.example` should align with the default configuration in `docker-compose.yml`.
    *   **Testing Variables:**
        *   `TEST_CLIENT_API_KEY`: Required for running E2E tests.

## Usage

### Running the Server
Ensure your `.env` file is configured correctly. Run the FastAPI application using Uvicorn:
```bash
poetry run uvicorn luthien_control.main:app --reload
```
The `--reload` flag enables auto-reloading when code changes are detected, useful during development.

## Generating Documentation
The project documentation is built using MkDocs.

To build the documentation locally:
```bash
poetry run mkdocs build --clean
```

To serve the documentation locally with live reload:
```bash
poetry run mkdocs serve
```
This will typically make the documentation available at `http://127.0.0.1:8000/`.

To deploy the documentation to GitHub Pages:
```bash
poetry run mkdocs gh-deploy
```

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
    *Ensure `OPENAI_API_KEY` and `TEST_CLIENT_API_KEY` are set in your environment or `.env` file.*
    
    **Important:** Before running E2E tests, you must add the test client API key to the database:
    ```bash
    # Use the script in the scripts directory
    poetry run python scripts/add_api_key.py --key-value="YOUR_TEST_CLIENT_API_KEY" --name="E2E Test Key"
    
    # Then run the E2E tests
    poetry run pytest -m e2e
    ```
*   **Run E2E tests against a deployed proxy server:**
    *Ensure `OPENAI_API_KEY` and `TEST_CLIENT_API_KEY` are set in your environment.*
    *(The [current development deployment](https://luthiencontrol-dev.up.railway.app/) is on railway and tracks the dev branch on github)*
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
*   E2E tests require the `OPENAI_API_KEY` and `TEST_CLIENT_API_KEY` environment variables and potentially others depending on the target backend and policies.
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