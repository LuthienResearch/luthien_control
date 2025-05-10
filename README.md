# Luthien Control


> **⚠️ EARLY DEVELOPMENT WARNING ⚠️**
>
> This project is currently in the early stages of development. It is **not yet suitable for production use**.
> Expect frequent updates, potential bugs, and **breaking changes** to the API and functionality without prior notice.
> Use at your own risk during this phase.

Luthien Control is a framework to implement AI Control policies on OpenAI-API compatible endpoints. The Luthien Control server is a proxy server that sits between clients and the AI backend, implementing AI Control policies on traffic that goes between them.

## Developer Documentation

Developer documentation is available here:

[![Documentation](https://img.shields.io/badge/documentation-view-brightgreen?style=for-the-badge)](https://luthienresearch.github.io/luthien_control/)

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
    *   Copy the example file: `cp .env.example .env`
    *   The example file includes reasonable defaults for local development that should work with the Docker setup.
    *   Edit the `.env` file if you need to customize any values.
    *   **Required Variables:**
        *   `BACKEND_URL`: The URL of the backend OpenAI-compatible API you want to proxy requests to (e.g., `https://api.openai.com/v1`).
        *   `OPENAI_API_KEY`: API key for the backend service (required if the backend needs authentication, like OpenAI).
    *   **Database Variables:**
        *   `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`: Database connection details for the main application database. The values for `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `DB_PORT` in your `.env` file are also used by `