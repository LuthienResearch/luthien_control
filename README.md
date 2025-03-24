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

- Run tests: `poetry run pytest`
- Format code: `poetry run black .`
- Sort imports: `poetry run isort .`
- Type checking: `poetry run mypy .`

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