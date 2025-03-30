import pytest
import asyncpg

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio

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
        result = await conn.fetchval("SELECT 1 FROM information_schema.tables WHERE table_name = 'interactions';")
        assert result == 1, "Table 'interactions' should exist after schema application."
        print("[Test] Schema verification successful ('interactions' table found)." )

        # Optional: Could add more checks for other tables or basic INSERT/SELECT
        # For now, just checking table existence is sufficient.

    except Exception as e:
        pytest.fail(f"Database test failed: {e}")
    finally:
        if conn:
            await conn.close()
            print("[Test] Database connection closed.") 