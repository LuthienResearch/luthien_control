#!/usr/bin/env python3
"""
Script to generate an Alembic migration for SQLModel tables.
"""

import subprocess
import sys

from dotenv import load_dotenv
from luthien_control.config.settings import Settings


def generate_migration(message="Initial sqlmodel tables"):
    """Run alembic revision with autogenerate."""
    # Load environment variables
    load_dotenv()

    # Check if required environment variables are set using Settings
    settings = Settings()
    missing_vars = []
    if not settings.get_postgres_user():
        missing_vars.append("DB_USER")
    if not settings.get_postgres_password():
        missing_vars.append("DB_PASSWORD")
    if not settings.get_postgres_db():
        missing_vars.append("DB_NAME")

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    # Run alembic revision with autogenerate
    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        print("Migration file generated successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating migration: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


if __name__ == "__main__":
    message = sys.argv[1] if len(sys.argv) > 1 else "Initial sqlmodel tables"
    success = generate_migration(message)
    sys.exit(0 if success else 1)
