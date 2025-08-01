.PHONY: help install setup-env setup-db full-setup \
	db-up db-down db-migrate \
	serve serve-dev \
	test test-e2e test-integration test-scripts test-all test-full \
	qc format lint typecheck security complexity \
	docs-build docs-serve docs-deploy \
	add-api-key list-api-keys \
	clean

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "📋 Setup & Installation:"
	@echo "  install        - Install dependencies with Poetry"
	@echo "  setup-env      - Copy example .env file"
	@echo "  setup-db       - Set up database (start container + migrate)"
	@echo "  full-setup     - Complete setup from scratch and start dev server"
	@echo ""
	@echo "🗄️  Database Management:"
	@echo "  db-up          - Start PostgreSQL container"
	@echo "  db-down        - Stop PostgreSQL container"
	@echo "  db-migrate     - Apply database migrations"
	@echo ""
	@echo "🚀 Development Server:"
	@echo "  serve          - Start production server"
	@echo "  serve-dev      - Start development server with auto-reload"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test           - Run unit tests with coverage (excludes e2e, integration, scripts)"
	@echo "  test-e2e       - Run end-to-end tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-scripts   - Run script tests"
	@echo "  test-all       - Run all tests including e2e, integration, and scripts"
	@echo "  test-full      - Run all tests with full coverage (including slower tests)"
	@echo ""
	@echo "🔧 Code Quality:"
	@echo "  qc             - Run complete quality control suite"
	@echo "  format         - Format code with ruff"
	@echo "  lint           - Check linting and apply fixes"
	@echo "  typecheck      - Run type checking with pyright"
	@echo "  security       - Run security scanning with bandit"
	@echo "  complexity     - Analyze code complexity with radon"
	@echo ""
	@echo "📚 Documentation: (Note: This is already handled by GH Actions, you generally don't need to run these)"
	@echo "  docs-build     - Build documentation"
	@echo "  docs-serve     - Serve documentation locally with live reload"
	@echo "  docs-deploy    - Deploy documentation to GitHub Pages"
	@echo ""
	@echo "🔑 API Key Management:"
	@echo "  add-api-key    - Add a new API key to the database"
	@echo "  list-api-keys  - List all API keys in the database"
	@echo ""
	@echo "🧹 Utilities:"
	@echo "  clean          - Clean up generated files and caches"

# =============================================================================
# Setup & Installation
# =============================================================================

# Install dependencies with Poetry
install:
	poetry install

# Copy example .env file (if it doesn't exist)
setup-env:
	@if [ ! -f .env ]; then \
		if [ -f docs/examples/.env.example ]; then \
			cp docs/examples/.env.example .env && echo "✅ Copied .env.example to .env"; \
		else \
			echo "⚠️  .env.example not found in docs/examples/"; \
		fi; \
	else \
		echo "✅ .env file already exists"; \
	fi

# Set up database (complete setup)
setup-db: db-up db-migrate
	@echo "✅ Database setup completed!"

# Complete setup from scratch and start dev server
full-setup: install setup-env setup-db
	@echo ""
	@echo "🚀 Starting development server..."
	@echo "✅ Full setup completed! Server starting on http://localhost:8000"
	@echo ""
	@echo "📝 Note: Make sure to configure your .env file with your API keys!"
	@echo ""
	poetry run uvicorn luthien_control.main:app --reload

# =============================================================================
# Database Management
# =============================================================================

# Start PostgreSQL container
db-up:
	docker compose up -d
	@echo "✅ PostgreSQL container started"

# Stop PostgreSQL container
db-down:
	docker compose down
	@echo "✅ PostgreSQL container stopped"

# Apply database migrations
db-migrate:
	poetry run alembic upgrade head
	@echo "✅ Database migrations applied"

# =============================================================================
# Development Server
# =============================================================================

# Start production server
serve:
	poetry run uvicorn luthien_control.main:app

# Start development server with auto-reload
serve-dev:
	poetry run uvicorn luthien_control.main:app --reload

# =============================================================================
# Testing
# =============================================================================

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

# =============================================================================
# Code Quality
# =============================================================================

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

# Run security scanning with bandit
security:
	poetry run bandit -r luthien_control/

# Analyze code complexity with radon
complexity:
	@echo "📊 Cyclomatic Complexity Analysis:"
	poetry run radon cc luthien_control/ -a -s
	@echo ""
	@echo "📊 Maintainability Index:"
	poetry run radon mi luthien_control/ -s

# =============================================================================
# Documentation
# =============================================================================

# Build documentation
docs-build:
	poetry run mkdocs build --clean

# Serve documentation locally with live reload
docs-serve:
	poetry run mkdocs serve

# Deploy documentation to GitHub Pages
docs-deploy:
	poetry run mkdocs gh-deploy

# =============================================================================
# API Key Management
# =============================================================================

# Add a new API key to the database (interactive)
add-api-key:
	@echo "Adding new API key to database..."
	poetry run python scripts/add_api_key.py

# List all API keys in the database
list-api-keys:
	poetry run python scripts/list_api_keys.py

# =============================================================================
# Utilities
# =============================================================================

# Clean up generated files and caches
clean:
	@echo "🧹 Cleaning up generated files and caches..."
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf site/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup completed!"
