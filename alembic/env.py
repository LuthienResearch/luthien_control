import logging  # Import logging
import os
import sys  # <-- Add this
from logging.config import fileConfig

# Add project root to Python path <-- Add these lines
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from alembic import context
from dotenv import load_dotenv
from luthien_control.db import sqlmodel_models  # noqa - Ensure models are registered
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

# Load environment variables from .env file
load_dotenv()

# Configure logging for Alembic script itself
logger = logging.getLogger(__name__)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set database connection URL from environment variables
# Prioritize DATABASE_URL
database_url = os.environ.get("DATABASE_URL")

# Determine the final URL to use
final_db_url = None

if database_url:
    logger.info("Using DATABASE_URL for Alembic connection.")
    # Ensure the URL format is compatible with synchronous psycopg2
    if database_url.startswith("postgresql+asyncpg://"):
        final_db_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif database_url.startswith("postgres://"):
        final_db_url = database_url.replace("postgres://", "postgresql://", 1)
        logger.info("Converted 'postgres://' URL to 'postgresql://'")
    else:
        final_db_url = database_url
elif os.environ.get("DB_USER") and os.environ.get("DB_PASSWORD") and os.environ.get("DB_NAME_NEW"):
    logger.warning("DATABASE_URL not set. Falling back to individual DB_* variables for Alembic.")
    # Fallback to individual variables if DATABASE_URL is not set
    postgres_user = os.environ.get("DB_USER")
    postgres_password = os.environ.get("DB_PASSWORD")
    postgres_host = os.environ.get("DB_HOST", "localhost")
    postgres_port = os.environ.get("DB_PORT", "5432")
    postgres_db = os.environ.get("DB_NAME_NEW")
    final_db_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
else:
    # Raise error if neither DATABASE_URL nor sufficient DB_* vars are set
    raise ValueError(
        "Database connection requires either DATABASE_URL environment variable "
        "or DB_USER, DB_PASSWORD, and DB_NAME_NEW to be set."
    )


# Set the final URL in the Alembic config
config.set_main_option("sqlalchemy.url", final_db_url)


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates a synchronous connection to the database to run migrations.
    """
    # Explicitly register the psycopg2 dialect to bypass entry point discovery issues
    # from sqlalchemy.dialects import postgresql, registry

    # Only register the postgresql dialect (not postgres) since that's what we're using in the URL
    # registry.register("postgresql", "sqlalchemy.dialects.postgresql.psycopg2", "PGDialect_psycopg2")
    # logger.info("Explicitly registered postgresql dialect for psycopg2.")

    connectable = create_engine(config.get_main_option("sqlalchemy.url"))

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
