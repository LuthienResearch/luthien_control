#!/bin/bash
# Script to start the monitoring stack for local development

echo "Starting Luthien Control with monitoring..."

# Check if docker-compose or docker compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "Error: Neither 'docker-compose' nor 'docker compose' command found"
    echo "Please install Docker and Docker Compose"
    exit 1
fi

# Start all services
echo "Starting services..."
$DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.loki.yml up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Check service status
echo "Service status:"
$DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.loki.yml ps

echo ""
echo "Services available at:"
echo "- Application: http://localhost:8000"
echo "- Grafana: http://localhost:3000"
echo "- Loki: http://localhost:3100"
echo ""
echo "To view logs:"
echo "$DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.loki.yml logs -f"