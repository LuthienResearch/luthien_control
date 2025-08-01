# Luthien Control

<div align="center">

[![Donate to Luthien on Manifund](https://img.shields.io/badge/Donate_To-Luthien-0118D8?style=flat)](https://manifund.org/projects/luthien)
[![Luthien Research](https://img.shields.io/badge/Luthien-Research-blue?style=flat&labelColor=0118D8&color=1B56FD)](https://luthienresearch.org/)
[![API Documentation](https://img.shields.io/badge/API-documentation-1B56FD?style=plastic)](https://luthienresearch.github.io/luthien_control/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/LuthienResearch/luthien_control)

**A flexible proxy server for implementing AI Control policies on OpenAI-compatible API endpoints**

> **⚠️ EARLY DEVELOPMENT WARNING**  
> This project is in early stages of development and not yet suitable for production use.  
> Expect frequent updates, potential bugs, and breaking API changes.

</div>

## What is Luthien Control?

Luthien Control is a powerful middleware proxy that sits between your applications and AI services (like OpenAI), giving you fine-grained control over AI interactions.

- 🛡️ **Monitor & Log** - Track all requests and responses for compliance and debugging
- 🔒 **Authenticate & Authorize** - Control who can access your AI services  
- 💰 **Manage Costs** - Set usage limits and monitor spending per user/team
- 🔄 **Transform Requests** - Modify prompts, enforce guidelines, or add context
- 🚦 **Apply Policies** - Implement safety filters, rate limiting, and custom business rules
- 🔌 **Stay Compatible** - Works with any OpenAI-compatible API

### Use Cases

- **Enterprise AI Governance** - Ensure AI usage complies with company policies
- **Multi-tenant SaaS** - Provide AI features to customers with usage controls
- **Research & Development** - Monitor and analyze AI model behavior
- **Cost Management** - Track and limit AI API spending across teams
- **Security & Compliance** - Audit AI interactions and filter sensitive data

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation) (for dependency management)
- Docker & Docker Compose (for local database)
- An OpenAI API key (or compatible service)

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/LuthienResearch/luthien_control.git
cd luthien_control

# Option 1: One step install
make full-install

# Option 2: Manual
poetry install

# Quick setup (copies example env file and starts database)
make setup-env
make setup-db
```

### 2. Configuration

Create a `.env` file with your settings:

```bash
# Backend API Configuration
BACKEND_URL=https://api.openai.com/v1  # Or your OpenAI-compatible endpoint
OPENAI_API_KEY=your-api-key-here        # Your backend API key

# Database (defaults work with Docker Compose)
DB_USER=luthien
DB_PASSWORD=luthien_password
DB_NAME=luthien_control
DB_HOST=localhost
DB_PORT=5432

# Optional: Development mode
RUN_MODE=dev  # Enables detailed error messages
```

### 3. Run the Server

```bash
# Start in development mode with auto-reload
make serve-dev

# Or use Poetry directly
poetry run uvicorn luthien_control.main:app --reload
```

Your proxy server is now running at `http://localhost:8000` 🎉

### 4. Test It Out

Send a request through your proxy:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-client-api-key" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 📦 One-Click Deployment

Deploy to Railway with pre-configured settings:

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/IXTECt?referralCode=ZazPnJ)

## 🛠️ Development

### Project Structure

```
luthien_control/
├── luthien_control/      # Main application code
│   ├── api/             # API endpoints and data models
│   ├── control_policy/  # Policy implementation
│   ├── core/            # Core functionality
│   ├── db/              # Database models and operations
│   └── proxy/           # Proxy server logic
├── tests/               # Test suite
├── scripts/             # Utility scripts
├── docs/                # Documentation
└── dev/                 # Development notes and plans
```

### Common Commands

```bash
# Code Quality
make qc          # Run complete quality control suite
make format      # Format code with ruff
make lint        # Check linting
make typecheck   # Run type checking

# Testing
make test        # Run unit tests
make test-e2e    # Run end-to-end tests
make test-all    # Run all tests

# Database
make db-up       # Start PostgreSQL container
make db-down     # Stop PostgreSQL container
make db-migrate  # Apply database migrations

# Documentation
make docs-serve  # Serve docs locally with live reload
make docs-build  # Build documentation
```

### Running Tests

```bash
# Unit tests (default)
poetry run pytest

# Integration tests
poetry run pytest -m integration

# E2E tests (requires API key and test setup)
poetry run python scripts/add_api_key.py --key-value="test-key" --name="E2E Test"
poetry run pytest -m e2e

# All tests with coverage
poetry run pytest --cov=luthien_control
```

### Contributing

We welcome contributions! Please:

1. Fork the repository and create a feature branch from `dev`
2. Follow our coding standards (Google-style docstrings, type hints)
3. Add tests for new functionality
4. Ensure all tests pass and code quality checks succeed
5. Submit a PR to the `dev` branch

See our [Contributing Guide](./CONTRIBUTING.md) for more details.

## 📚 Documentation

- **[API Documentation](https://luthienresearch.github.io/luthien_control/)** - Full API reference
- **[Policy Examples](./docs/examples/)** - Sample policy configurations
- **[Development Guide](./dev/)** - Architecture and development notes

## 🔧 Advanced Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKEND_URL` | OpenAI-compatible API endpoint | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | API key for backend service | Required |
| `TOP_LEVEL_POLICY_NAME` | Name of policy to apply from DB | None |
| `POLICY_FILEPATH` | Path to JSON policy file | None |
| `DATABASE_URL` | Full PostgreSQL connection URL | Built from DB_* vars |
| `RUN_MODE` | Set to "dev" for detailed errors | None |
| `TEST_CLIENT_API_KEY` | API key for E2E tests | None |

### Database Setup

The project uses PostgreSQL with SQLModel (SQLAlchemy + Pydantic) and Alembic for migrations.

```bash
# Start database container
docker compose up -d

# Apply migrations
poetry run alembic upgrade head

# Create a new migration
poetry run alembic revision --autogenerate -m "Description"
```

### Custom Policies

Policies control how requests and responses are processed. Create custom policies by:

1. Implementing the `ControlPolicy` interface
2. Registering your policy class
3. Configuring it via JSON or database (by e.g. adding it to a SerialPolicy with a config)

See [Policy Documentation](./docs/examples/sample_policy.json) for examples.

## 🤝 Support & Community

- **Issues & Bugs**: [GitHub Issues](https://github.com/LuthienResearch/luthien_control/issues)
- **Discussions**: [GitHub Discussions](https://github.com/LuthienResearch/luthien_control/discussions)
- **Updates**: Follow [Luthien Research](https://luthienresearch.org/)
- **Support Us**: [Donate on Manifund](https://manifund.org/projects/luthien)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./luthien_control/LICENSE) file for details.

---

<div align="center">
Built with ❤️ by <a href="https://luthienresearch.org/">Luthien Research</a>
</div>