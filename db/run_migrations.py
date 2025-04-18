import logging
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.errors  # Import specific errors
from dotenv import load_dotenv
from psycopg2 import sql

# Determine project root assuming script is in db/
PROJECT_ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"

SCHEMA_MIGRATIONS_TABLE_NAME = "schema_migrations"
# Assuming the script creating the table follows this naming convention
SCHEMA_MIGRATIONS_CREATION_SCRIPT = "002_add_migration_tracking_table.sql"


def get_db_connection():
    """Establishes and returns a database connection using env vars.
    Prioritizes DATABASE_URL if available, otherwise uses individual DB_* vars.
    """
    database_url = os.getenv("DATABASE_URL")
    try:
        if database_url:
            # Log parts of the URL for debugging (mask password)
            try:
                from urllib.parse import urlparse

                parsed = urlparse(database_url)
                masked_url = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}{parsed.path}"
                logging.info(f"Attempting to connect using DATABASE_URL: {masked_url}")
            except Exception:
                logging.info("Attempting to connect using DATABASE_URL (details hidden).")
            conn = psycopg2.connect(dsn=database_url)
        else:
            logging.info("DATABASE_URL not found, attempting connection using individual DB_* variables.")
            # Check for required individual variables if DATABASE_URL is not set
            required_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                logging.error(f"Missing required DB_* variables when DATABASE_URL is not set: {missing_vars}")
                sys.exit(1)

            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST", "localhost"),  # Keep default for local
                port=os.getenv("DB_PORT", "5432"),  # Keep default for local
            )

        logging.info("Database connection established.")
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during DB connection: {e}")
        sys.exit(1)


def ensure_schema_migrations_table(conn):
    """Checks if the schema_migrations table exists and creates it if not."""
    try:
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                );
            """,
                (SCHEMA_MIGRATIONS_TABLE_NAME,),
            )
            table_exists = cur.fetchone()[0]

            if table_exists:
                logging.info(f"'{SCHEMA_MIGRATIONS_TABLE_NAME}' table already exists.")
                return True

            # Table doesn't exist, create it
            logging.info(f"'{SCHEMA_MIGRATIONS_TABLE_NAME}' table not found. Creating it now...")
            creation_script_path = MIGRATIONS_DIR / SCHEMA_MIGRATIONS_CREATION_SCRIPT
            if not creation_script_path.exists():
                logging.error(f"Migration script '{SCHEMA_MIGRATIONS_CREATION_SCRIPT}' not found!")
                return False

            sql_content = creation_script_path.read_text()
            cur.execute(sql_content)
            logging.info(f"Successfully executed script: {SCHEMA_MIGRATIONS_CREATION_SCRIPT}")

            # Crucially, record this script's execution *immediately* after creating the table
            insert_sql = sql.SQL("INSERT INTO {} (version) VALUES (%s)").format(
                sql.Identifier(SCHEMA_MIGRATIONS_TABLE_NAME)
            )
            cur.execute(insert_sql, (SCHEMA_MIGRATIONS_CREATION_SCRIPT,))
            logging.info(f"Successfully recorded: {SCHEMA_MIGRATIONS_CREATION_SCRIPT}")
            return True

    except psycopg2.Error as e:
        logging.error(f"Database error during schema_migrations table check/creation: {e}")
        # Attempt to rollback if any transaction was started implicitly (though autocommit should prevent)
        try:
            conn.rollback()
        except psycopg2.Error:
            pass  # Ignore rollback errors if already handled or not in transaction
        return False
    except Exception as e:
        logging.error(f"Unexpected error during schema_migrations table check/creation: {e}")
        return False


def get_applied_migrations(conn) -> set[str]:
    """Queries the database to get the set of already applied migration versions.
    Assumes the 'schema_migrations' table exists.
    """
    applied = set()
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT version FROM {}").format(sql.Identifier(SCHEMA_MIGRATIONS_TABLE_NAME)))
            applied.update(row[0] for row in cur.fetchall())
            logging.info(f"Found {len(applied)} applied migrations in the database.")
    except psycopg2.errors.UndefinedTable:
        # This should ideally not happen if ensure_schema_migrations_table runs first
        logging.error(f"'{SCHEMA_MIGRATIONS_TABLE_NAME}' table not found unexpectedly during query.")
        # Treat as no migrations applied, but log error
        return set()
    except psycopg2.Error as e:
        logging.error(f"Error querying applied migrations: {e}")
        # Depending on the error, we might want to exit or return empty
        return set()  # Return empty set on other query errors for now
    return applied


def get_available_migrations() -> list[str]:
    """Gets a sorted list of available .sql migration files from the migrations directory."""
    if not MIGRATIONS_DIR.is_dir():
        logging.error(f"Migrations directory not found: {MIGRATIONS_DIR}")
        return []

    migrations = sorted(
        [
            f.name
            for f in MIGRATIONS_DIR.glob("*.sql")
            if f.is_file() and f.name[0].isdigit()  # Basic check for sequential naming
        ]
    )
    logging.info(f"Found {len(migrations)} available migration files.")
    return migrations


def run_migration(conn, migration_file: Path):
    """Executes a single migration script. Returns True on success, False on failure."""
    version = migration_file.name
    logging.info(f"Executing migration script: {version}...")
    try:
        with conn.cursor() as cur:
            sql_content = migration_file.read_text()
            cur.execute(sql_content)
        logging.info(f"Successfully executed script: {version}")
        return True
    except psycopg2.Error as e:
        logging.error(f"Error executing migration script {version}: {e}")
        logging.error("SQL Content:")
        logging.error(migration_file.read_text())  # Log SQL on error
        # Attempt to rollback if a transaction was somehow started
        try:
            conn.rollback()
        except psycopg2.Error:
            pass
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during script execution {version}: {e}")
        return False


def main():
    # Configure basic logging to show INFO messages on the console
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    load_dotenv()
    available = get_available_migrations()
    if not available:
        logging.info("No migration files found.")
        sys.exit(0)

    conn = None
    all_successful = True
    try:
        conn = get_db_connection()
        # Connection already logs its status

        # Ensure the tracking table exists
        if not ensure_schema_migrations_table(conn):
            logging.error("Failed to ensure schema migrations table exists. Aborting.")
            sys.exit(1)

        # Get applied migrations (table is guaranteed to exist now)
        applied = get_applied_migrations(conn)

        logging.info(f"Found {len(available)} migration files. Checking status...")

        # Process each available migration individually, in order
        for migration_name in available:
            migration_file = MIGRATIONS_DIR / migration_name

            if migration_name in applied:
                logging.info(f"[Skipped] {migration_name} (already applied)")
                continue

            # If not applied, attempt to run it
            logging.info(f"[Applying] {migration_name}...")
            if run_migration(conn, migration_file):
                # If successful, record it immediately
                logging.info(f"  Recording migration: {migration_name}...")
                try:
                    with conn.cursor() as cur:
                        insert_sql = sql.SQL("INSERT INTO {} (version) VALUES (%s)").format(
                            sql.Identifier(SCHEMA_MIGRATIONS_TABLE_NAME)
                        )
                        cur.execute(insert_sql, (migration_name,))
                        conn.commit()
                    logging.info(f"[Success] {migration_name}")
                except psycopg2.Error as insert_err:
                    logging.error(
                        f"[CRITICAL] Failed to record migration {migration_name} "
                        f"after successful execution: {insert_err}"
                    )
                    logging.error("  The schema may be in an inconsistent state. Manual intervention required.")
                    all_successful = False
                    break  # Stop processing further migrations on critical record error
            else:
                # run_migration failed and logged the error
                logging.error(f"[Failed] {migration_name}. Stopping further migrations.")
                all_successful = False
                break  # Stop processing further migrations on execution failure

        if all_successful:
            logging.info("Migration check complete. All migrations processed successfully or already applied.")
        else:
            logging.error("Migration process stopped due to errors.")
            sys.exit(1)  # Exit with error code if any migration failed

    except Exception as e:
        logging.exception(f"An unexpected error occurred during the migration process: {e}")
        sys.exit(1)
    finally:
        if conn and not conn.closed:
            conn.close()
            logging.info("Database connection closed.")


if __name__ == "__main__":
    # Set up logging before calling main
    main()
