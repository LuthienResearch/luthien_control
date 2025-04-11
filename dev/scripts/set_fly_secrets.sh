#!/bin/bash

# Strict mode
set -euo pipefail
IFS=$'\\n\\t'

# Check if flyctl is installed
if ! command -v fly &> /dev/null; then
    echo "Error: flyctl command not found. Please install it first." >&2
    exit 1
fi

# Default .env file path
DEFAULT_ENV_FILE=".env"
ENV_FILE="${1:-$DEFAULT_ENV_FILE}" # Use first argument or default

# Check if the .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file '$ENV_FILE' not found." >&2
    echo "Usage: $0 [path/to/your/.env]" >&2
    exit 1
fi

echo "Setting secrets from '$ENV_FILE' for Fly app..."

# Read the .env file line by line
# Skip empty lines and lines starting with #
# Use process substitution to avoid subshell issues with variables
while IFS= read -r line || [[ -n "$line" ]]; do
    # Trim leading/trailing whitespace
    trimmed_line=$(echo "$line" | awk '{$1=$1};1')

    # Skip comments and empty lines
    if [[ -z "$trimmed_line" || "$trimmed_line" == \#* ]]; then
        continue
    fi

    # Check if the line contains '='
    if [[ "$trimmed_line" != *"="* ]]; then
      echo "Warning: Skipping malformed line (no '=' found): $trimmed_line" >&2
      continue
    fi

    # Split KEY=VALUE
    # Use parameter expansion to split at the first '=' only
    key="${trimmed_line%%=*}"
    value="${trimmed_line#*=}"

    # Ensure key is not empty
    if [[ -z "$key" ]]; then
      echo "Warning: Skipping line with empty key: $trimmed_line" >&2
      continue
    fi

    echo "Setting secret for key: $key"

    # Set the secret using flyctl
    # Use --stage to prevent immediate deployment restarts
    if ! fly secrets set "$key=$value" --stage; then
        echo "Error: Failed to set secret for key '$key'. Aborting." >&2
        # Consider whether to exit immediately or continue with others
        exit 1 # Exit on first failure for safety
    fi

done < "$ENV_FILE"

echo "Secrets staged successfully."
echo "Run 'fly deploy' to apply the changes and restart your application."
echo "Alternatively, run 'fly secrets deploy' to apply secrets without a full deploy." 