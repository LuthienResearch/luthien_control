# Luthien Control Monitoring Setup

This directory contains the configuration for Grafana Loki monitoring integration.

## Local Development

### Starting the Monitoring Stack

1. Start Loki and Grafana:
```bash
docker-compose -f docker-compose.yml -f docker-compose.loki.yml up -d
```

2. Access Grafana at http://localhost:3000
   - Default credentials: admin/admin (or anonymous access is enabled)
   - Loki datasource is pre-configured

3. The application will automatically send logs to Loki if `LOKI_URL` is set (defaults to http://loki:3100 in Docker)

### Testing Logs

Run the test script to generate sample logs:
```bash
poetry run python scripts/test_logging.py
```

### Querying Logs in Grafana

1. Go to Explore in Grafana
2. Select the Loki datasource
3. Use LogQL queries like:
   - `{application="luthien_control"}` - All application logs
   - `{application="luthien_control"} |= "error"` - Error logs
   - `{application="luthien_control", environment="development"}` - Development logs

## Railway Deployment

The Railway deployment uses separate services for each component:

1. **Main Application**: Deployed from the root Dockerfile
2. **Loki**: Deployed from `railway/loki/`
3. **Grafana**: Deployed from `railway/grafana/`

### Environment Variables

Set these in Railway:

For the main application:
- `LOKI_URL`: Set to `http://loki.railway.internal:3100`

For Grafana:
- `LOKI_INTERNAL_URL`: Set to `http://loki.railway.internal:3100`

### Railway Service Setup

1. Create three services in Railway:
   - `luthien-control` (main app)
   - `loki` 
   - `grafana`

2. Configure each service:
   - Point each to the appropriate directory/Dockerfile
   - Set environment variables as needed
   - Ensure they're on the same private network

3. The services will communicate via Railway's internal network using `.railway.internal` domains.

## Log Retention

By default, Loki is configured to retain logs for 7 days (168h). This can be adjusted in the Loki configuration.