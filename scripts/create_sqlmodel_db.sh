#!/bin/bash
# Script to create a new database for SQLModel and grant permissions to the luthien user

set -e  # Exit immediately if a command exits with a non-zero status

# Load environment variables
if [ -f "../.env" ]; then
    source ../.env
else
    echo "Warning: No .env file found. Make sure your environment variables are set."
fi

# Required environment variables
DB_USER=${DB_USER:-postgres}  # Default to postgres if not set
DB_NAME=${DB_NAME:-luthien_sqlmodel}  # Default name if not set
APP_USER=${APP_USER:-luthien}  # The application user that needs permissions
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}

# Check if PGPASSWORD is set either in env or as argument
if [ -z "$DB_PASSWORD" ] && [ -z "$PGPASSWORD" ]; then
    echo "Please enter the password for PostgreSQL user '$DB_USER':"
    read -s DB_PASSWORD
    export PGPASSWORD=$DB_PASSWORD
else
    # If DB_PASSWORD is set, use it as PGPASSWORD
    PGPASSWORD=${PGPASSWORD:-$DB_PASSWORD}
    export PGPASSWORD
fi

echo "Creating database $DB_NAME..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME;"

echo "Granting permissions to $APP_USER on $DB_NAME..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $APP_USER;"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "GRANT ALL PRIVILEGES ON SCHEMA public TO $APP_USER;"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO $APP_USER;"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO $APP_USER;"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON FUNCTIONS TO $APP_USER;"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TYPES TO $APP_USER;"

echo "Database $DB_NAME created and permissions granted to $APP_USER."
echo "You can now set the DB_NAME environment variable to $DB_NAME in your .env file."

# Clean up password from environment
unset PGPASSWORD

exit 0