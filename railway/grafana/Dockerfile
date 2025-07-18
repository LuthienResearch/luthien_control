FROM grafana/grafana:latest

# Copy provisioning files
COPY provisioning /etc/grafana/provisioning

# Verify provisioning files are copied (this will show in build logs)
RUN ls -la /etc/grafana/provisioning/ && \
    ls -la /etc/grafana/provisioning/datasources/ && \
    cat /etc/grafana/provisioning/datasources/loki.yaml

# Set anonymous access for development (adjust for production)
ENV GF_AUTH_ANONYMOUS_ENABLED=true
ENV GF_AUTH_ANONYMOUS_ORG_ROLE=Admin

# Enable debug logging for provisioning
ENV GF_LOG_LEVEL=debug
ENV GF_LOG_FILTERS=provisioning:debug

# Explicitly set the provisioning path
ENV GF_PATHS_PROVISIONING=/etc/grafana/provisioning