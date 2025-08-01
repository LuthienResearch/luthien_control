# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test Commands
- This project uses `poetry` for environment and package management. Most commands should start with `poetry`. ***DO NOT TRY TO RUN RAW `python`; ALWAYS USE `poetry run python...`***
- Run all tests: `poetry run pytest`
- Run specific test: `poetry run pytest tests/path/to/test_file.py::test_function_name`
- Run with coverage: `poetry run pytest --cov=luthien_control`
- Run E2E tests: `poetry run pytest -m e2e`
- Format code: `poetry run ruff format .`
- Check linting: `poetry run ruff check .`
- Type checking: `poetry run pyright`
- Complexity analysis: `poetry run radon cc luthien_control/ -a -s`
- Use poetry run to run commands in the development environment

## Quality Validation Before Committing
Code qc tools are defined in the Makefile: `make (format|lint|typecheck|test)`. `make qc` runs all of the tools.


## Code Style
- Mandatory TDD workflow (skeleton → tests → implementation)
- Python 3.11+, follow PEP 8
- Max Line length: 120 characters
- Use type hints for all function signatures
- Organize imports with standard order (typing first)
- Use async functions for I/O-bound tasks
- Error handling: Specific exception types, HTTPException for API errors
- Google-style docstrings for modules, classes, and functions
- Never add comments about editing the code (e.g. "Added X", "Y is now handled by Z"). That information belongs in chat channels with the current developer, not the actual codebase.

## Testing Principles
- Unit tests should be as simple as possible; mock only when needed to avoid external dependencies, or when mocking significantly reduces the complexity of the test, otherwise prefer using Real Stuff
- Test *critical* behavior. Generally avoid testing for specific strings or incidental properties of returned values or side effects unless there's a strong reason to do so.