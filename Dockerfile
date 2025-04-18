# Stage 1: Builder
FROM python:3.11-slim as builder

# Set Poetry version
ARG POETRY_VERSION=2.0.1

# Install pipx and Poetry
RUN pip install --no-cache-dir pipx
RUN pipx install poetry==${POETRY_VERSION}

# Set path to include poetry executable
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Builder Stage: Install system deps here for potential cache benefits, but they're essential in runtime stage
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Configure Poetry to not create virtualenvs
RUN poetry config virtualenvs.create false

# Copy dependency definition files
COPY pyproject.toml poetry.lock ./

# Install dependencies in builder (useful cache, but won't copy site-packages)
RUN poetry install --no-interaction --no-ansi --no-root --without dev

# Stage 2: Runtime
FROM python:3.11-slim

ARG POETRY_VERSION=2.0.1
RUN pip install --no-cache-dir pipx
RUN pipx install poetry==${POETRY_VERSION}
ENV PATH="/root/.local/bin:$PATH"

# Runtime Stage: Install system deps needed for psycopg2 install HERE
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

RUN poetry config virtualenvs.create false

WORKDIR /app

# Copy project definition files needed by poetry run
COPY pyproject.toml poetry.lock ./

# Install dependencies directly in runtime stage
RUN poetry install --no-interaction --no-ansi --no-root --without dev

# Copy the application code and db scripts
COPY luthien_control/ ./luthien_control/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "uvicorn", "luthien_control.main:app", "--host", "0.0.0.0", "--port", "8000"] 