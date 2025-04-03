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

# Configure Poetry to not create virtualenvs
RUN poetry config virtualenvs.create false

# Copy dependency definition files
COPY pyproject.toml poetry.lock ./

# Install dependencies
# --no-root: Don't install the project itself, only dependencies
# --without dev: Exclude development dependencies
RUN poetry install --no-interaction --no-ansi --no-root --without dev

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy installed dependencies from builder stage
# Packages are installed in the system site-packages because virtualenvs.create=false
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy the application code
COPY luthien_control/ ./luthien_control/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Assuming the FastAPI app instance is named 'app' in 'luthien_control.main'
# Adjust 'luthien_control.main:app' if your entry point is different
CMD ["python", "-m", "uvicorn", "luthien_control.main:app", "--host", "0.0.0.0", "--port", "8000"] 