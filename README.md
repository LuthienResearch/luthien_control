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