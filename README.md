[![Donate to Luthien on Manifund](https://img.shields.io/badge/Donate_To-Luthien-0118D8?style=flat)](https://manifund.org/projects/luthien)

[![Luthien Research](https://img.shields.io/badge/Luthien-Research-blue?style=flat&labelColor=0118D8&color=1B56FD)](https://luthienresearch.org/)

[![API Documentation](https://img.shields.io/badge/API-documentation-1B56FD?style=plastic)](https://luthienresearch.github.io/luthien_control/)

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/LuthienResearch/luthien_control)

> **⚠️ EARLY DEVELOPMENT WARNING ⚠️**
>
> This project is currently in the early stages of development. It is **not yet suitable for production use**.
> Expect frequent updates, potential bugs, and **breaking changes** to the API and functionality without prior notice.
> Use at your own risk during this phase.

# Luthien Control

Luthien Control is a framework to implement AI Control policies on OpenAI-API compatible endpoints. The Luthien Control server is a proxy server that sits between clients and the AI backend, implementing AI Control policies on traffic that goes between them.

## Contributing

- The main development branch is [dev](https://github.com/luthienResearch/luthien_control/tree/dev) - point PRs here.
- `ruff` is used for linting and formatting
- Google-style docstrings
- Unit tests are in `tests`, new code should generally come with new tests. We're targeting 90% coverage.

## Technology Stack

- **Language:** Python (3.11+)
- **Package Management:** Poetry
- **Web Framework:** FastAPI
- **Server:** Uvicorn
- **Database:**
  - PostgreSQL (using `asyncpg`) - Legacy system
  - SQLModel (SQLAlchemy + Pydantic) with Alembic - New system (in transition)
- **HTTP Client:** HTTPX
- **Configuration:** Environment variables via `python-dotenv`
- **Linting/Formatting:** Ruff
- **Security Scanning:** Bandit
- **Testing:** Pytest, `pytest-cov`
- **Local DB:** Docker Compose

# Directory Structure

## Code

- [`luthien_control/`](./luthien_control/): Main package code (submodules: `proxy/`, `db/`, `config/`, `logging/`, `core/`, etc.).
- [`tests/`](./tests/): Top-level test directory mirroring `luthien_control`.

## Development

- **[`pyproject.toml`](./pyproject.toml)**: The primary configuration file for the Python project, mostly managed by Poetry. It defines project metadata, dependencies, and settings for tools like Ruff, Pytest, and Pyright.
- **[`CHANGELOG.md`](./CHANGELOG.md)**: Logs changes.
- **[`dev/`](./dev/)**: Development tracking files (Mostly used to keep track of plans and progress on those plans during development).
- **[`scripts/`](./scripts/)**: Helper scripts (database creation, log rotation, etc.).
- **[`.pre-commit-config.yaml`](./.pre-commit-config.yaml)**: Configures `pre-commit` hooks for linting, formatting, and other automated checks before code is committed.
- **[`codecov.yml`](./codecov.yml)**: Codecov coverage reporting.

### Documentation

- **[`mkdocs.yml`](./mkdocs.yml)**: Configures MkDocs, the static site generator used for building project documentation.
- **[`docs/`](./docs/)**: Generated static documentation site.

### Database

- **[`alembic.ini`](./alembic.ini)**: Alembic config for database migration
- **[`alembic/`](./alembic/)**: Database migration files for SQLModel.

### AI Assistant Support

- **[`CLAUDE.md`](./CLAUDE.md)**: Claude Code guidelines
- **[`.cursor/rules/`](./.cursor/rules/)**: Cursor assistant guidelines.

### CICD

- **[`.github/workflows/`](./.github/workflows/)**: Github Actions for code analysis, coverage, testing, etc.

### Docker

- **[`Dockerfile`](./Dockerfile)** & **[`docker-compose.yml`](./docker-compose.yml)**: Used by Docker to build and run the application and its services (like the database) in containers.
- **[`.dockerignore`](./.dockerignore)**: Specifies which files and directories to exclude from the Docker build context. This is a standard Docker file and cannot be merged into other Docker configurations.

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry
- Docker and Docker Compose (for local database)

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
    cp docs/examples/.env.example .env
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
    - The example file `docs/examples/.env.example` includes reasonable defaults for local development that should work with the Docker setup.
    - Edit the `.env` file if you need to customize any values.
    - **Env Variables**
      - `POLICY_FILEPATH`: If set, `POLICY_FILEPATH` should be a json defining a SerializedPolicy which will be used as the control policy on the server. Otherwise, see `TOP_LEVEL_POLICY_NAME`
      - `TOP_LEVEL_POLICY_NAME`: The name of the top-level policy configured in your DB that the server will apply to all requests/responses passing through
      - `BACKEND_URL`: The URL of the backend OpenAI-compatible API you want to proxy requests to (e.g., `https://api.openai.com/v1`).
      - `OPENAI_API_KEY`: API key for the backend service (required if the backend needs authentication, like OpenAI).(NOTE: THIS IS DEPRECATED, BACKEND API KEYS SHOULD NOW BE SET TO ENV VARIABLES SPECIFIED PER-POLICY, SEE `AddApiKeyHeaderFromEnv`)
    - **Database Variables:**
      - `DATABASE_URL`: Full postgres DB connection URL. If this is not set, the `DB_*` env vars will be used instead.
      - `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`: Database connection details for the main application database. The values for `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `DB_PORT` in your `.env` file are also used by `docker-compose.yml` to set up the local PostgreSQL container. The defaults in `/docs/examples/.env.example` should align with the default configuration in `docker-compose.yml`.
      - `APP_USER`: This is only used by the `create_sqlmodel_db.sh` script for initializing the database. Gives the postgres `APP_USER` required permissions on the created DB.
    - **Testing Variables:**
      - `TEST_CLIENT_API_KEY`: Required for running E2E tests. This will be used as the client key to authenticate _against the Luthien Control Server_ (NOT the actual backend, e.g. OpenAI)
        **Development Variables:**
      - `RUN_MODE`: if set to `"dev"`, return detailed error messages on internal server errors. Likely other changes in the future.

## Usage

### Running the Server

#### Local Development

Ensure your `.env` file is configured correctly. Run the FastAPI application using Uvicorn:

```bash
poetry run uvicorn luthien_control.main:app --reload
```

The `--reload` flag enables auto-reloading when code changes are detected, useful during development.

#### Railway

Just set your OpenAI API-compatible backend and a valid API key:

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/IXTECt?referralCode=ZazPnJ)

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

- **Unit Tests (`unit` marker or no marker):** Run by default (`poetry run pytest`). They typically mock external dependencies and use `.env.test` if it exists.
- **Integration Tests (`integration` marker):** Excluded by default. These tests might interact with local services like the database defined in `docker-compose.yml` and use `.env`.
- **End-to-End (E2E) Tests (`e2e` marker):** Excluded by default. These tests run against a live proxy server (either local or deployed) which connects to a _real backend API_ (e.g., OpenAI). They require network access, `OPENAI_API_KEY` in the environment, and potentially incur API costs.

**Running Tests:**

- **Run default tests (unit tests):**
  ```bash
  poetry run pytest
  ```
- **Run integration tests:**
  ```bash
  poetry run pytest -m integration
  ```
- **Run End-to-End (E2E) tests against a locally started server:**
  _Ensure `OPENAI_API_KEY` and `TEST_CLIENT_API_KEY` are set in your environment or `.env` file._

  **Important:** Before running E2E tests, you must add the test client API key to the database:

  ```bash
  # Use the script in the scripts directory
  poetry run python scripts/add_api_key.py --key-value="YOUR_TEST_CLIENT_API_KEY" --name="E2E Test Key"

  # Then run the E2E tests
  poetry run pytest -m e2e
  ```

- **Run E2E tests against a deployed proxy server:**
  _Ensure `OPENAI_API_KEY` and `TEST_CLIENT_API_KEY` are set in your environment._
  _(The [current development deployment](https://luthiencontrol-dev.up.railway.app/) is on railway and tracks the dev branch on github)_
  ```bash
  poetry run pytest -m e2e --e2e-target-url https://your-deployed-proxy.example.com
  ```
- **Run all non-E2E tests (Unit & Integration) with coverage:**
  ```bash
  poetry run pytest --cov=luthien_control -m "not e2e"
  ```
- **Run all tests (Unit, Integration & E2E) with coverage:**
  ```bash
  poetry run pytest --cov=luthien_control
  ```
  _(Note: Coverage reporting might be less meaningful for E2E tests involving separate processes.)_

**Test Configuration:**

- Tests without the `integration` or `e2e` marker primarily use environment variables defined in `.env.test` (if it exists).
- Integration tests use environment variables from `.env`.
- E2E tests require the `OPENAI_API_KEY` and `TEST_CLIENT_API_KEY` environment variables and potentially others depending on the target backend and policies.
- The E2E local server fixture defaults to using `https://api.openai.com/v1` as the `BACKEND_URL` unless overridden by an existing environment variable.

### Linting & Formatting

This project uses Ruff for linting and formatting.

- Check formatting and linting: `poetry run ruff check .`
- Apply formatting: `poetry run ruff format .`

### Type Checking

This project uses Pyright for static type checking. The goal is to maintain zero type errors in both the
package and tests (`luthien_control/` and `tests/`)

- Run Pyright: `poetry run pyright`

### Security Scanning

Bandit is used to check for common security vulnerabilities.

- Run Bandit: `poetry run bandit -r luthien_control/`

### Code Complexity Analysis

Radon is used to analyze code complexity (e.g., cyclomatic complexity). This helps identify potentially complex and hard-to-maintain code.

- Check complexity: `poetry run radon cc luthien_control/ -a -s` (shows average and sorted results)
- Check maintainability index: `poetry run radon mi luthien_control -s`

-
