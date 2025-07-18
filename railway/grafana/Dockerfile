FROM grafana/grafana:latest

# Copy provisioning files
COPY provisioning /etc/grafana/provisioning

# Set anonymous access for development (adjust for production)
ENV GF_AUTH_ANONYMOUS_ENABLED=true
ENV GF_AUTH_ANONYMOUS_ORG_ROLE=Admin