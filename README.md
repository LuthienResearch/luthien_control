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
*   **Database:** PostgreSQL (using `asyncpg`)
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
        *   `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`: Database connection details for the *main* application database (if needed in the future, currently unused by core proxy but potentially used by tests/fixtures).
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

### Directory Structure
*   `luthien_control/`: Main package code (submodules: `proxy/`, `db/`, `config/`, `logging/`, etc.).
*   `tests/`: Top-level test directory mirroring `luthien_control`.
*   `dev/`: Development tracking files (`ProjectPlan.md`, `current_context.md`, `development_log.md`, `ToDo.md`).
*   `dev/scripts/`: Helper scripts (e.g., log rotation).
*   `docker-compose.yml`: Configuration for local development database.
*   `.env.example`: Example environment variable file.
*   `pyproject.toml`: Project metadata and dependencies (Poetry).
*   `.cursor/rules/`: AI assistant guidelines.
