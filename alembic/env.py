import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

# Load environment variables from .env file
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set database connection URL from environment variables
if "DB_USER" not in os.environ or "DB_PASSWORD" not in os.environ:
    raise ValueError("Environment variables DB_USER and DB_PASSWORD must be set")

# Override sqlalchemy.url based on loaded environment variables
postgres_user = os.environ.get("DB_USER")
postgres_password = os.environ.get("DB_PASSWORD")
postgres_host = os.environ.get("DB_HOST", "localhost")
postgres_port = os.environ.get("DB_PORT", "5432")
postgres_db = os.environ.get("DB_NAME_NEW")

if not postgres_db:
    raise ValueError("Environment variable DB_NAME_NEW must be set")

section = config.config_ini_section
config.set_section_option(section, "DB_USER", postgres_user)
config.set_section_option(section, "DB_PASSWORD", postgres_password)
config.set_section_option(section, "DB_HOST", postgres_host)
config.set_section_option(section, "DB_PORT", postgres_port)
config.set_section_option(section, "DB_NAME_NEW", postgres_db)

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
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
