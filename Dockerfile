FROM python:3.11-slim

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy the entire project first
COPY . .

# Install dependencies and the package itself
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Expose the port
EXPOSE 8000

# Run the application using poetry run
CMD ["poetry", "run", "python", "run.py"]
