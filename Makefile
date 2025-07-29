.PHONY: runqc format lint typecheck test help

# Default target
help:
	@echo "Available targets:"
	@echo "  runqc     - Run complete quality control suite"
	@echo "  format    - Format code with ruff"
	@echo "  lint      - Check linting and apply fixes"
	@echo "  typecheck - Run type checking with pyright"
	@echo "  test      - Run tests with coverage"

# Complete quality control suite
runqc: format lint typecheck test
	@echo "✅ Quality control suite completed successfully!"

# Format code
format:
	poetry run ruff format .

# Check linting and apply fixes
lint:
	poetry run ruff check . --fix --unsafe-fixes

# Run type checking
typecheck:
	poetry run pyright

# Run tests with coverage
test:
	poetry run pytest --cov=luthien_control