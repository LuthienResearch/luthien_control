# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test Commands
- This project uses `poetry` for environment and package management. Most commands should start with `poetry`. ***DO NOT TRY TO RUN RAW `python`; ALWAYS USE `poetry run python...`***
- Lots of useful commands are defined in the Makefile; `make help` for a summary.

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
- **YAGNI**: Don't build fallbacks for hypothetical scenarios. Fail fast on unexpected input rather than attempting to handle "just in case" formats.

## Testing Principles
- Unit tests should be as simple as possible; mock only when needed to avoid external dependencies, or when mocking significantly reduces the complexity of the test, otherwise prefer using Real Stuff
- Test *critical* behavior. Generally avoid testing for specific strings or incidental properties of returned values or side effects unless there's a strong reason to do so.