import logging
import os
import socket
import subprocess
import sys
import time
from typing import Any, AsyncGenerator, Dict

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from luthien_control.config.settings import Settings
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.registry import POLICY_CLASS_TO_NAME
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.db.control_policy_crud import (
    get_policy_config_by_name,
    update_policy,
)

# Add imports needed for policy creation
# Add new imports for async engine and session management
from luthien_control.db.database_async import (
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.db.sqlmodel_models import ControlPolicy
from sqlalchemy.exc import IntegrityError  # Add this import

# Load .env file for local development environment variables
# This ensures OPENAI_API_KEY and potentially BACKEND_URL are loaded if defined there
# In CI/deployed envs, these should be set directly as environment variables
load_dotenv()

# Configure logging for the helper function
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)  # Basic config for visibility

E2E_POLICY_NAME = "e2e_test_policy"

settings = Settings()  # Instantiate settings globally


async def _ensure_e2e_policy_exists():
    """Connects to DB and ensures the E2E test policy exists and is configured correctly."""
    # Settings instance is now global
    engine_created = False
    logger.info(f"Ensuring E2E policy '{E2E_POLICY_NAME}' exists in database...")
    try:
        # Use the same env vars the server process will use
        # Create the engine instead of the pool
        engine = await create_db_engine()
        if not engine:
            raise RuntimeError("Failed to create database engine for E2E setup.")
        engine_created = True

        # Use the async session generator
        async with get_db_session() as session:
            existing_policy = await get_policy_config_by_name(session, E2E_POLICY_NAME)

            # Define the desired state
            desired_config = {
                "policies": [
                    {
                        "type": POLICY_CLASS_TO_NAME[ClientApiKeyAuthPolicy],
                        "config": {"name": "E2E_ClientAPIKeyCheck"},
                    },
                    {
                        "type": POLICY_CLASS_TO_NAME[AddApiKeyHeaderPolicy],
                        "config": {"name": "E2E_AddBackendKey"},
                    },
                    {
                        "type": POLICY_CLASS_TO_NAME[SendBackendRequestPolicy],
                        "config": {"name": "E2E_ForwardRequest"},
                    },
                ]
            }
            desired_description = "E2E Test Policy: Adds backend key -> Sends request."

            if existing_policy:
                # Check if update is needed
                if (
                    existing_policy.config != desired_config
                    or existing_policy.description != desired_description
                    or not existing_policy.is_active  # Ensure it's active
                ):
                    logger.info(f"Policy '{E2E_POLICY_NAME}' (ID: {existing_policy.id}) exists but needs update.")
                    update_data = ControlPolicy(
                        id=existing_policy.id,
                        name=existing_policy.name,
                        type=existing_policy.type,
                        config=desired_config,
                        is_active=True,
                        description=desired_description,
                        created_at=existing_policy.created_at,
                    )
                    updated_policy = await update_policy(session, existing_policy.id, update_data)
                    if updated_policy:
                        logger.info(f"Successfully updated policy '{E2E_POLICY_NAME}'.")
                    else:
                        logger.error(f"Failed to update policy '{E2E_POLICY_NAME}'.")
                        # Optionally raise an error to fail the test setup
                        raise RuntimeError(f"Failed to update E2E policy '{E2E_POLICY_NAME}'")
                else:
                    logger.info(f"Policy '{E2E_POLICY_NAME}' exists and is up-to-date.")
            else:
                logger.info(f"Policy '{E2E_POLICY_NAME}' not found by initial check. Attempting creation...")
                policy_to_create = ControlPolicy(
                    name=E2E_POLICY_NAME,
                    config=desired_config,
                    type=POLICY_CLASS_TO_NAME[CompoundPolicy],
                    is_active=True,
                    description=desired_description,
                )
                session.add(policy_to_create)
                try:
                    logger.info(f"Attempting to commit new policy '{E2E_POLICY_NAME}'...")
                    await session.commit()
                    await session.refresh(policy_to_create)
                    logger.info(
                        f"Successfully committed and refreshed new policy '{E2E_POLICY_NAME}' "
                        f"(ID: {policy_to_create.id})."
                    )
                    # Policy created successfully by this process
                    # No further action needed in this block
                except IntegrityError as ie:
                    # This likely means another process created it concurrently
                    logger.warning(
                        f"Commit failed for '{E2E_POLICY_NAME}' due to IntegrityError (likely race condition): "
                        f"{ie}. Rolling back."
                    )
                    await session.rollback()  # Rollback the failed transaction
                    logger.info(f"Fetching policy '{E2E_POLICY_NAME}' again after IntegrityError...")
                    existing_policy = await get_policy_config_by_name(session, E2E_POLICY_NAME)
                    if existing_policy:
                        logger.info(
                            f"Successfully fetched policy '{E2E_POLICY_NAME}' (ID: {existing_policy.id}) "
                            "after concurrent creation."
                        )
                        # Optional: Check if the concurrently created policy needs an update
                        if (
                            existing_policy.config != desired_config
                            or existing_policy.description != desired_description
                            or not existing_policy.is_active
                        ):
                            logger.warning(
                                f"Concurrently created policy '{E2E_POLICY_NAME}' needs an update. Applying update..."
                            )
                            # Apply the update logic here (similar to the initial update check)
                            update_data = ControlPolicy(
                                id=existing_policy.id,
                                name=existing_policy.name,
                                type=existing_policy.type,
                                config=desired_config,
                                is_active=True,
                                description=desired_description,
                                created_at=existing_policy.created_at,  # Keep original creation time
                            )
                            updated_policy = await update_policy(session, existing_policy.id, update_data)
                            if updated_policy:
                                logger.info(f"Successfully updated concurrently created policy '{E2E_POLICY_NAME}'.")
                            else:
                                logger.error(f"Failed to update concurrently created policy '{E2E_POLICY_NAME}'.")
                                raise RuntimeError(
                                    f"Failed to update concurrently created E2E policy '{E2E_POLICY_NAME}'"
                                )
                        else:
                            logger.info(f"Concurrently created policy '{E2E_POLICY_NAME}' is already up-to-date.")
                    else:
                        # This case is problematic - commit failed but policy still not found
                        logger.error(
                            f"Policy '{E2E_POLICY_NAME}' not found even after commit failed with IntegrityError. "
                            "DB state issue?",
                            exc_info=True,
                        )
                        raise RuntimeError(
                            f"Failed to create or find E2E policy '{E2E_POLICY_NAME}' after IntegrityError."
                        )

                except Exception as commit_exc:  # Catch other commit issues
                    logger.error(
                        f"DATABASE COMMIT FAILED for policy '{E2E_POLICY_NAME}' with unexpected error: {commit_exc}",
                        exc_info=True,
                    )
                    try:
                        await session.rollback()
                    except Exception as rb_exc:
                        logger.error(f"Failed to rollback after unexpected commit error: {rb_exc}", exc_info=True)
                    # Re-raise a specific error to fail the test setup clearly
                    raise RuntimeError(
                        f"Failed to commit new E2E policy '{E2E_POLICY_NAME}' due to unexpected error: {commit_exc}"
                    ) from commit_exc

                # Policy creation (or handling of concurrent creation) finished.
                # We can assume the policy exists and is configured correctly at this point.

    except Exception as e:
        # Catch other errors like connection issues, etc.
        logger.exception(f"General error ensuring E2E policy exists: {e}")
        raise  # Re-raise to fail the test setup
    finally:
        # Close the engine if it was created
        if engine_created:
            await close_db_engine()
            logger.info("Closed temporary DB engine used for E2E policy setup.")


# --- Fixtures ---


@pytest.fixture(scope="session")
def openai_api_key() -> str:
    """Fixture to provide the OpenAI API key from environment variables."""
    key = settings.get_openai_api_key()
    if not key:
        pytest.fail(
            "Missing required environment variable: OPENAI_API_KEY. Ensure it is set in your environment or .env file."
        )
    return key


def _find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture(scope="function")
async def live_local_proxy_server(openai_api_key: str) -> AsyncGenerator[str, None]:
    """
    Starts a local instance of the FastAPI proxy server in a subprocess
    for function-scoped E2E tests.

    Yields:
        The base URL (http://127.0.0.1:PORT) of the running local server.
    """
    port = _find_free_port()
    host = "127.0.0.1"

    # Prepare environment variables for the subprocess
    # Use a separate dict, don't modify os.environ directly
    server_env: Dict[str, Any] = {}

    # Copy relevant env vars from current environment if they exist
    # These might be set by CI or a local .env file
    for var in [
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME_NEW",
        "DATABASE_URL",
        "MAIN_DB_POOL_MIN_SIZE",
        "MAIN_DB_POOL_MAX_SIZE",
        "TEST_CLIENT_API_KEY",
        "BACKEND_URL",
        "LOG_LEVEL",
    ]:
        value = os.getenv(var)  # Check actual env first
        if value is not None:
            server_env[var] = value

    # Ensure the necessary policy exists in the DB before starting server
    await _ensure_e2e_policy_exists()

    # Explicitly set required env vars for the E2E server,
    # ensuring the correct values are used for the test server process.
    # Use the fixture value for OPENAI_API_KEY.
    server_env["OPENAI_API_KEY"] = openai_api_key  # From fixture

    # Default to real OpenAI backend for E2E tests unless overridden by system env
    # Use the settings getter, which checks the env var
    backend_url = settings.get_backend_url() or "https://api.openai.com/v1"
    server_env["BACKEND_URL"] = backend_url

    # Tell the server process to load the specific policy created for E2E tests
    server_env["TOP_LEVEL_POLICY_NAME"] = "e2e_test_policy"

    # Define base URL after preparing environment
    base_url = f"http://{host}:{port}"

    # Command to start the server using uvicorn
    # Use sys.executable to ensure the same Python interpreter is used
    # Add --log-level warning to reduce noise during tests
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "luthien_control.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]

    print(f"\nStarting local server: {' '.join(cmd)}")
    # Print the *actual* backend URL being used by the server process
    print(f"Local server env BACKEND_URL: {server_env.get('BACKEND_URL')}")
    process = None
    try:
        # Start the server process
        process = subprocess.Popen(cmd, env=server_env, stdout=sys.stdout, stderr=sys.stderr)

        # Wait for the server to be ready
        # Poll the health check endpoint
        max_wait_seconds = 15
        start_time = time.time()
        server_ready = False
        with httpx.Client() as health_client:
            while time.time() - start_time < max_wait_seconds:
                if process.poll() is not None:  # Check if process terminated prematurely
                    pytest.fail(f"Local server process terminated unexpectedly with code {process.poll()}. Check logs.")
                try:
                    response = health_client.get(f"{base_url}/health")
                    if response.status_code == 200:
                        print(f"Local server ready at {base_url}")
                        server_ready = True
                        break
                except httpx.ConnectError:
                    time.sleep(0.5)  # Wait before retrying connection
                except Exception as e:
                    print(f"Health check error: {e}")
                    time.sleep(0.5)

        if not server_ready:
            pytest.fail(f"Local server failed to start within {max_wait_seconds} seconds.")

        # Yield the base URL to the tests
        yield base_url

    finally:
        # Teardown: Stop the server process
        if process and process.poll() is None:  # Check if process exists and is running
            print(f"\nTerminating local server (PID: {process.pid})...")
            process.terminate()
            try:
                process.wait(timeout=5)  # Wait for termination
                print("Local server terminated gracefully.")
            except subprocess.TimeoutExpired:
                print("Server did not terminate gracefully, killing...")
                process.kill()
                process.wait()  # Ensure it's killed
                print("Local server killed.")
        elif process:
            print(
                f"Local server process (PID: {process.pid}) already terminated with code {process.poll()}."
            )  # Already stopped


@pytest.fixture(scope="function")
def proxy_target_url(request: pytest.FixtureRequest, live_local_proxy_server: str) -> str:
    """
    Provides the base URL for the proxy server to be tested.
    Uses the --e2e-target-url command line option if provided,
    otherwise uses the URL from the live_local_proxy_server fixture.
    """
    target_url_option = request.config.getoption("--e2e-target-url")
    if target_url_option:
        print(f"\nUsing provided target URL: {target_url_option}")
        # Basic validation
        if not target_url_option.startswith(("http://", "https://")):
            pytest.fail(f"Invalid --e2e-target-url: '{target_url_option}'. Must start with http:// or https://")
        return target_url_option
    else:
        print(f"\nUsing local server URL: {live_local_proxy_server}")
        return live_local_proxy_server


@pytest.fixture(scope="session")
def client_api_key() -> str:
    """Fixture to provide the client API key for testing from environment variables."""
    key = os.getenv("TEST_CLIENT_API_KEY")  # Test-specific key read directly
    if not key:
        pytest.fail(
            "Missing required environment variable: TEST_CLIENT_API_KEY. "
            "Ensure it is set in your environment or .env file."
        )
    return key


@pytest_asyncio.fixture(scope="function")
async def e2e_client(
    proxy_target_url: str, openai_api_key: str, client_api_key: str
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Provides an httpx.AsyncClient configured to talk to the target proxy URL
    with the necessary client and backend API key authentication headers.
    """
    headers = {
        "Authorization": f"Bearer {client_api_key}",
        "Accept": "application/json",
    }
    # Increase default timeouts for potentially slower E2E interactions
    timeout = httpx.Timeout(10.0, connect=5.0, read=30.0, write=10.0)

    async with httpx.AsyncClient(base_url=proxy_target_url, headers=headers, timeout=timeout) as client:
        # Optional: Perform a quick health check before yielding
        try:
            health_response = await client.get("/health")
            health_response.raise_for_status()  # Raise exception for 4xx/5xx status codes
            print(f"Successfully connected to health endpoint at {proxy_target_url}/health")
        except httpx.RequestError as exc:
            pytest.fail(f"Failed to connect to target proxy health endpoint {proxy_target_url}/health: {exc}")
        except httpx.HTTPStatusError as exc:
            pytest.fail(
                f"Target proxy health endpoint {proxy_target_url}/health returned "
                f"error status {exc.response.status_code}: {exc.response.text}"
            )

        yield client
        # httpx.AsyncClient is automatically closed by the async context manager
        print(f"\nClosed httpx client for {proxy_target_url}")
