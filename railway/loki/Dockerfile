FROM grafana/loki:3.0.0

# Copy custom configuration
COPY config.yaml /etc/loki/config.yaml

# Use our custom configuration
CMD ["-config.file=/etc/loki/config.yaml"]