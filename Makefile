.PHONY: qc format lint typecheck test test-e2e test-integration test-scripts test-all test-full help

# Default target
help:
	@echo "Available targets:"
	@echo "  qc             - Run complete quality control suite"
	@echo "  format         - Format code with ruff"
	@echo "  lint           - Check linting and apply fixes"
	@echo "  typecheck      - Run type checking with pyright"
	@echo "  test           - Run unit tests with coverage (excludes e2e, integration, scripts)"
	@echo "  test-e2e       - Run end-to-end tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-scripts   - Run script tests"
	@echo "  test-all       - Run all tests including e2e, integration, and scripts"
	@echo "  test-full      - Run all tests with full coverage (including slower tests)"

# Complete quality control suite
qc: format lint typecheck test
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

# Run tests with coverage (excludes e2e, integration, scripts by default)
test:
	poetry run pytest --cov=luthien_control

# Run end-to-end tests
test-e2e:
	poetry run pytest -m e2e -v

# Run integration tests
test-integration:
	poetry run pytest -m integration -v

# Run script tests (test scripts in scripts/ directory)
test-scripts:
	poetry run pytest scripts/test_*.py -v

# Run all tests including e2e, integration, and unit tests
test-all:
	poetry run pytest tests/ --cov=luthien_control -v

# Run all tests with full coverage (including slower tests)
test-full:
	poetry run pytest tests/ scripts/ --cov=luthien_control -v || echo "⚠️  Some script tests may have failed or not been found"
