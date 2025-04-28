# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test Commands
- Run all tests: `poetry run pytest`
- Run specific test: `poetry run pytest tests/path/to/test_file.py::test_function_name`
- Run with coverage: `poetry run pytest --cov=luthien_control`
- Run E2E tests: `poetry run pytest -m e2e`
- Format code: `poetry run ruff format .`
- Check linting: `poetry run ruff check .`
- Complexity analysis: `poetry run radon cc luthien_control/ -a -s`

## Code Style
- Mandatory TDD workflow (skeleton → tests → implementation)
- Python 3.11+, follow PEP 8
- Line length: 120 characters
- Use type hints for all function signatures
- Prefer functional components over classes
- Organize imports with standard order (typing first)
- Use Pydantic models for validation
- Use async functions for I/O-bound tasks
- Error handling: Specific exception types, HTTPException for API errors
- Naming: lowercase_with_underscores, descriptive with auxiliary verbs
- Docstrings for modules, classes, and functions