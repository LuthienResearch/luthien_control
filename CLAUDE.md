# Luthien Control Framework Development Guide

## Core Commands
- **Install Dependencies**: `poetry install`
- **Run Server**: `python -m luthien_control`
- **Run Tests**: `poetry run pytest`
- **Run Single Test**: `poetry run pytest luthien_control/test_file.py::test_function`
- **Format Code**: `poetry run black . && poetry run isort .`
- **Type Check**: `poetry run mypy .`
- **Lint Code**: `poetry run ruff check . --fix`

## Code Style Guidelines
- **Python**: Use Python 3.9+ with strict type hints
- **Formatting**: Black (default config), isort for imports
- **Documentation**: Docstrings for all classes and functions
- **Imports**: Group standard lib, third-party libs, local modules
- **Naming**: Classes=PascalCase, functions/vars=snake_case, constants=UPPER_SNAKE_CASE
- **Error Handling**: Catch specific exceptions, add context with logging
- **Logging**: Use appropriate log levels (debug, info, warning, error)

## Repository Structure
- **luthien_control/**: Main Python package
  - **proxy/**: Proxy server implementation
  - **policies/**: Policy engine and safety rules
  - **logging/**: Logging and monitoring tools
  - **utils/**: Utility functions