# Luthien Control Framework

A proxy server for monitoring and controlling AI model API interactions. This framework provides organizations with practical AI safety tools to leverage model capabilities while mitigating risks associated with frontier AI deployment.

## Features

- Transparent HTTP proxy server for AI model APIs
- Request/response monitoring and logging
- Configurable policy engine for safety rules
- Authentication and API key management
- Comprehensive logging and monitoring capabilities

## Setup

1. Ensure you have Python 3.9+ and Poetry installed
2. Clone the repository
3. Install dependencies:
   ```bash
   poetry install
   ```

## Development

### Testing

The project includes comprehensive test suites, including integration tests that can run against both local and deployed instances.

#### Running Tests

- Run all tests: `poetry run pytest`
- Run only unit tests: `poetry run pytest -m "not integration"`
- Run integration tests:
  ```bash
  # Test against local server (default)
  poetry run pytest -v -m integration

  # Test against deployed server
  poetry run pytest -v -m integration --env=deployed

  # Test against both environments
  poetry run pytest -v -m integration --env=both
  ```

#### Test Environment Selection

The `--env` option controls which environment to test against:
- `--env=local` (default): Tests against a local server instance
- `--env=deployed`: Tests against the deployed server
- `env=both`: Tests against both environments

Note: Some tests (e.g., security-sensitive tests) may be skipped when running against the deployed instance.

### Development Tools

This project uses `ruff`, `bandit`, `mypy`, and `pre-commit` to ensure code quality, security, and consistency.

**Setup:**

After cloning the repository and running `poetry install`, activate the pre-commit hooks:

```bash
poetry run pre-commit install
```

This will automatically run checks on your code whenever you make a commit.

**Manual Checks:**

You can also run the checks manually:

- **Format code:** `poetry run ruff format .`
- **Lint & fix code:** `poetry run ruff check . --fix`
- **Type check:** `poetry run mypy luthien_control/ tests/`
- **Security scan:** `poetry run bandit -c pyproject.toml` (uses config from pyproject.toml)

**Configuration:**

- Code formatting, linting (`ruff`), security (`bandit`), and type checking (`mypy`) are configured in `pyproject.toml`.
- Pre-commit hooks are defined in `.pre-commit-config.yaml`.
- The project uses a maximum line length of 120 characters.

## Deployment

### Deploying to Fly.io

Luthien Control is configured for easy deployment to Fly.io. Follow these steps:

1. Install the Fly.io CLI:
   ```bash
   # macOS
   brew install flyctl

   # Linux
   curl -L https://fly.io/install.sh | sh
   ```

2. Login to Fly:
   ```bash
   fly auth login
   ```

3. Launch your app (first-time deployment):
   ```bash
   fly launch
   ```

4. For subsequent deployments:
   ```bash
   fly deploy
   ```

5. Set up environment secrets:
   ```bash
   fly secrets set OPENAI_API_KEY="your-api-key"
   ```

6. View your app logs:
   ```bash
   fly logs
   ```

7. Access your app:
   ```
   https://luthien-control.fly.dev
   ```

To use a custom domain, you can set it up with:
```bash
fly certs create your-domain.com
```

## Project Structure

```
luthien_control/
├── proxy/           # Proxy server implementation
├── policies/        # Policy engine and rules
├── logging/         # Logging and monitoring
└── utils/           # Utility functions
```

## License

[License information to be added]
