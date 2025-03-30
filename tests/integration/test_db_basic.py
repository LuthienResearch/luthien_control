import asyncpg
import pytest

# Mark all tests in this module as async and integration
pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_db_connection_and_schema(test_db_session):
    """Tests connection to the temporary database and verifies schema application.

    Args:
        test_db_session: The DSN string for the temporary test database, provided by the fixture.
    """
    conn = None
    try:
        # The test_db_session argument *is* the DSN string yielded by the fixture.
        dsn = test_db_session
        print(f"\n[Test] Connecting to test database: {dsn}")
        conn = await asyncpg.connect(dsn=dsn)
        print("[Test] Connection successful.")

        # Simple query to check if a key table from the schema exists
        # This implicitly verifies that the schema was applied
        print("[Test] Verifying schema by checking 'interactions' table...")
        result = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'interactions';"
        )
        assert result == 1, (
            "Table 'interactions' should exist after schema application."
        )
        print("[Test] Schema verification successful ('interactions' table found).")

        # Optional: Could add more checks for other tables or basic INSERT/SELECT
        # For now, just checking table existence is sufficient.

    except Exception as e:
        pytest.fail(f"Database test failed: {e}")
    finally:
        if conn:
            await conn.close()
            print("[Test] Database connection closed.")


async def test_db_log_insertion(test_db_session):
    """Tests that log_request_response inserts a record correctly into the test DB."""
    # Get connection settings, forcing use of the test DB DSN
    # We need the components to create the pool AND the DSN for direct connection
    # Let's parse the DSN - assumes format postgresql://user:pass@host:port/db
    dsn = test_db_session
    from urllib.parse import urlparse

    parsed_dsn = urlparse(dsn)

    # Import necessary functions HERE, before use
    import json

    from luthien_control.db.database import (
        DBSettings,
        close_db_pool,
        create_db_pool,
        get_db_pool,
        log_request_response,
    )

    settings = DBSettings(
        db_user=parsed_dsn.username or "user",
        db_password=parsed_dsn.password or "password",
        db_host=parsed_dsn.hostname or "localhost",
        db_port=parsed_dsn.port or 5432,
        db_name=parsed_dsn.path.lstrip("/") if parsed_dsn.path else "test_db",
        # Keep pool sizes small for testing
        db_pool_min_size=1,
        db_pool_max_size=1,
    )

    pool = None
    conn = None
    try:
        # Create a real pool connected to the test DB
        # Ensure any previous pool is closed (important if tests run in sequence modifying global state)
        await close_db_pool()
        await create_db_pool(settings)
        pool = get_db_pool()  # Should work now

        # Sample data
        client_ip = "192.168.1.50"
        request_data = {
            "method": "GET",
            "url": "/integration/test",
            "headers": {"Accept": "text/plain"},
            "body": None,
            "processing_time_ms": 75,
        }
        response_data = {
            "status_code": 200,
            "headers": {"Content-Type": "text/plain"},
            "body": "Integration Test OK",
        }

        # Call the function under test
        await log_request_response(
            pool=pool,
            request_data=request_data,
            response_data=response_data,
            client_ip=client_ip,
        )

        # Verify insertion directly
        conn = await asyncpg.connect(dsn=dsn)
        record = await conn.fetchrow(
            "SELECT * FROM request_log ORDER BY timestamp DESC LIMIT 1"
        )

        assert record is not None, "No record found in request_log"
        assert record["client_ip"] == client_ip
        assert record["request_method"] == request_data["method"]
        assert record["request_url"] == request_data["url"]
        assert json.loads(record["request_headers"]) == request_data["headers"]
        assert (
            record["request_body"] == request_data["body"]
        )  # Assuming None maps to NULL
        assert record["response_status_code"] == response_data["status_code"]
        assert json.loads(record["response_headers"]) == response_data["headers"]
        assert record["response_body"] == response_data["body"]
        assert record["processing_time_ms"] == request_data["processing_time_ms"]

        print("\n[Test] Log insertion verification successful.")

    except Exception as e:
        pytest.fail(f"Log insertion test failed: {e}")
    finally:
        if conn:
            await conn.close()
            print("[Test] Direct DB connection closed.")
        # Ensure pool is closed to avoid resource leaks between tests
        await close_db_pool()
        print("[Test] DB Pool closed.")
