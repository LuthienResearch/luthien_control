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
from luthien_control.control_policy.add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from luthien_control.control_policy.registry import POLICY_CLASS_TO_NAME
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.control_policy.serial_policy import SerialPolicy
from luthien_control.control_policy.set_backend_policy import SetBackendPolicy
from luthien_control.db.control_policy_crud import (
    get_policy_config_by_name,
    update_policy,
)
from luthien_control.db.database_async import (
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.db.exceptions import LuthienDBQueryError
from luthien_control.db.sqlmodel_models import ControlPolicy
from luthien_control.settings import Settings
from sqlalchemy.exc import IntegrityError

# Load .env file for local development environment variables
# This ensures OPENAI_API_KEY and potentially BACKEND_URL are loaded if defined there
# In CI/deployed envs, these should be set directly as environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

E2E_DB_POLICY_NAME = "e2e_db_test_policy"

settings = Settings()  # Instantiate settings globally


async def _ensure_e2e_policy_exists():
    """Connects to DB and ensures the E2E test policy exists and is configured correctly."""
    engine_created = False
    logger.info(f"Ensuring E2E policy '{E2E_DB_POLICY_NAME}' exists in database...")
    try:
        engine = await create_db_engine()
        if not engine:
            raise RuntimeError("Failed to create database engine for E2E setup.")
        engine_created = True

        async with get_db_session() as session:
            try:
                existing_policy = await get_policy_config_by_name(session, E2E_DB_POLICY_NAME)
            except LuthienDBQueryError:
                # Policy doesn't exist yet
                existing_policy = None

            # Define the desired state - matching e2e_policy.json structure
            desired_config = {
                "policies": [
                    {
                        "type": POLICY_CLASS_TO_NAME[ClientApiKeyAuthPolicy],
                        "config": {"name": "E2E_ClientAPIKeyCheck"},
                    },
                    {
                        "type": POLICY_CLASS_TO_NAME[LeakedApiKeyDetectionPolicy],
                        "config": {"name": "E2E_LeakedKeyCheck"},
                    },
                    {
                        "type": POLICY_CLASS_TO_NAME[AddApiKeyHeaderFromEnvPolicy],
                        "config": {"name": "E2E_AddBackendKey", "api_key_env_var_name": "OPENAI_API_KEY"},
                    },
                    {
                        "type": POLICY_CLASS_TO_NAME[SetBackendPolicy],
                        "config": {"name": "E2E_SetBackend", "backend_url": "https://api.openai.com/v1/"},
                    },
                    {
                        "type": POLICY_CLASS_TO_NAME[SendBackendRequestPolicy],
                        "config": {"name": "E2E_ForwardRequest"},
                    },
                ]
            }
            desired_description = (
                "E2E DB Test Policy: Client auth -> Leaked key check -> "
                "Adds backend key -> Sets backend -> Sends request."
            )

            if existing_policy:
                # Check if update is needed
                if (
                    existing_policy.config != desired_config
                    or existing_policy.description != desired_description
                    or not existing_policy.is_active
                ):
                    logger.info(f"Policy '{E2E_DB_POLICY_NAME}' (ID: {existing_policy.id}) exists but needs update.")
                    update_data = ControlPolicy(
                        id=existing_policy.id,
                        name=existing_policy.name,
                        type=existing_policy.type,
                        config=desired_config,
                        is_active=True,
                        description=desired_description,
                        created_at=existing_policy.created_at,
                    )
                    assert existing_policy.id is not None
                    updated_policy = await update_policy(session, existing_policy.id, update_data)
                    if updated_policy:
                        logger.info(f"Successfully updated policy '{E2E_DB_POLICY_NAME}'.")
                    else:
                        raise RuntimeError(f"Failed to update E2E policy '{E2E_DB_POLICY_NAME}'")
                else:
                    logger.info(f"Policy '{E2E_DB_POLICY_NAME}' exists and is up-to-date.")
            else:
                logger.info(f"Policy '{E2E_DB_POLICY_NAME}' not found. Creating...")
                policy_to_create = ControlPolicy(
                    name=E2E_DB_POLICY_NAME,
                    config=desired_config,
                    type=POLICY_CLASS_TO_NAME[SerialPolicy],
                    is_active=True,
                    description=desired_description,
                )
                session.add(policy_to_create)
                try:
                    await session.commit()
                    await session.refresh(policy_to_create)
                    logger.info(f"Successfully created policy '{E2E_DB_POLICY_NAME}' (ID: {policy_to_create.id}).")
                except IntegrityError as ie:
                    logger.warning(f"IntegrityError creating policy: {ie}. Checking if it exists...")
                    await session.rollback()
                    try:
                        existing_policy = await get_policy_config_by_name(session, E2E_DB_POLICY_NAME)
                        logger.info(f"Policy '{E2E_DB_POLICY_NAME}' was created concurrently.")
                    except LuthienDBQueryError:
                        raise RuntimeError(f"Failed to create or find E2E policy '{E2E_DB_POLICY_NAME}'.")

    except Exception as e:
        logger.exception(f"Error ensuring E2E policy exists: {e}")
        raise
    finally:
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
async def live_local_proxy_server_file_based(openai_api_key: str) -> AsyncGenerator[str, None]:
    """
    Starts a local instance of the FastAPI proxy server using a file-based policy
    (e2e_policy.json) for function-scoped E2E tests.

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
        "DB_NAME",
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

    # Explicitly set required env vars for the E2E server,
    # ensuring the correct values are used for the test server process.
    # Use the fixture value for OPENAI_API_KEY.
    server_env["OPENAI_API_KEY"] = openai_api_key  # From fixture

    # Default to real OpenAI backend for E2E tests unless overridden by system env
    # Use the settings getter, which checks the env var
    backend_url = settings.get_backend_url() or "https://api.openai.com"
    server_env["BACKEND_URL"] = backend_url

    # Tell the server process to load the specific policy file for E2E tests
    server_env["POLICY_FILEPATH"] = "tests/e2e/e2e_policy.json"

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


@pytest_asyncio.fixture(scope="function")
async def live_local_proxy_server_db_based(openai_api_key: str) -> AsyncGenerator[str, None]:
    """
    Starts a local instance of the FastAPI proxy server using a database-based policy
    for function-scoped E2E tests.

    Yields:
        The base URL (http://127.0.0.1:PORT) of the running local server.
    """
    # Ensure the database policy exists before starting the server
    await _ensure_e2e_policy_exists()

    port = _find_free_port()
    host = "127.0.0.1"

    # Prepare environment variables for the subprocess
    server_env: Dict[str, Any] = {}

    # Copy relevant env vars from current environment if they exist
    for var in [
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DATABASE_URL",
        "MAIN_DB_POOL_MIN_SIZE",
        "MAIN_DB_POOL_MAX_SIZE",
        "TEST_CLIENT_API_KEY",
        "BACKEND_URL",
        "LOG_LEVEL",
    ]:
        value = os.getenv(var)
        if value is not None:
            server_env[var] = value

    # Set required env vars for the E2E server
    server_env["OPENAI_API_KEY"] = openai_api_key
    backend_url = settings.get_backend_url() or "https://api.openai.com"
    server_env["BACKEND_URL"] = backend_url

    # Tell the server process to load the specific DB policy for E2E tests
    server_env["TOP_LEVEL_POLICY_NAME"] = E2E_DB_POLICY_NAME

    # Define base URL after preparing environment
    base_url = f"http://{host}:{port}"

    # Command to start the server
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

    print(f"\nStarting local server with DB policy: {' '.join(cmd)}")
    print(f"Local server env BACKEND_URL: {server_env.get('BACKEND_URL')}")
    print(f"Using DB policy: {E2E_DB_POLICY_NAME}")
    process = None
    try:
        # Start the server process
        process = subprocess.Popen(cmd, env=server_env, stdout=sys.stdout, stderr=sys.stderr)

        # Wait for the server to be ready
        max_wait_seconds = 15
        start_time = time.time()
        server_ready = False
        with httpx.Client() as health_client:
            while time.time() - start_time < max_wait_seconds:
                if process.poll() is not None:
                    pytest.fail(f"Local server process terminated unexpectedly with code {process.poll()}. Check logs.")
                try:
                    response = health_client.get(f"{base_url}/health")
                    if response.status_code == 200:
                        print(f"Local server ready at {base_url}")
                        server_ready = True
                        break
                except httpx.ConnectError:
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Health check error: {e}")
                    time.sleep(0.5)

        if not server_ready:
            pytest.fail(f"Local server failed to start within {max_wait_seconds} seconds.")

        yield base_url

    finally:
        # Teardown: Stop the server process
        if process and process.poll() is None:
            print(f"\nTerminating local server (PID: {process.pid})...")
            process.terminate()
            try:
                process.wait(timeout=5)
                print("Local server terminated gracefully.")
            except subprocess.TimeoutExpired:
                print("Server did not terminate gracefully, killing...")
                process.kill()
                process.wait()
                print("Local server killed.")
        elif process:
            print(f"Local server process (PID: {process.pid}) already terminated with code {process.poll()}.")


@pytest.fixture(scope="function")
def proxy_target_url_file_based(request: pytest.FixtureRequest, live_local_proxy_server_file_based: str) -> str:
    """
    Provides the base URL for the proxy server to be tested (file-based policy).
    Uses the --e2e-target-url command line option if provided,
    otherwise uses the URL from the live_local_proxy_server_file_based fixture.
    """
    target_url_option = request.config.getoption("--e2e-target-url")
    if target_url_option is not None:  # Explicitly check for None
        assert isinstance(target_url_option, str)  # Make type checker happy
        print(f"\nUsing provided target URL: {target_url_option}")
        # Basic validation
        if not target_url_option.startswith(("http://", "https://")):
            pytest.fail(f"Invalid --e2e-target-url: '{target_url_option}'. Must start with http:// or https://")
        return target_url_option
    else:
        print(f"\nUsing local server URL (file-based): {live_local_proxy_server_file_based}")
        return live_local_proxy_server_file_based


@pytest.fixture(scope="function")
def proxy_target_url_db_based(request: pytest.FixtureRequest, live_local_proxy_server_db_based: str) -> str:
    """
    Provides the base URL for the proxy server to be tested (database-based policy).
    Uses the --e2e-target-url command line option if provided,
    otherwise uses the URL from the live_local_proxy_server_db_based fixture.
    """
    target_url_option = request.config.getoption("--e2e-target-url")
    if target_url_option is not None:  # Explicitly check for None
        assert isinstance(target_url_option, str)  # Make type checker happy
        print(f"\nUsing provided target URL: {target_url_option}")
        # Basic validation
        if not target_url_option.startswith(("http://", "https://")):
            pytest.fail(f"Invalid --e2e-target-url: '{target_url_option}'. Must start with http:// or https://")
        return target_url_option
    else:
        print(f"\nUsing local server URL (db-based): {live_local_proxy_server_db_based}")
        return live_local_proxy_server_db_based


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
async def e2e_client_file_based(
    proxy_target_url_file_based: str, client_api_key: str
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Provides an httpx.AsyncClient configured to talk to the file-based policy proxy.
    """
    headers = {
        "Authorization": f"Bearer {client_api_key}",
        "Accept": "application/json",
    }
    # Increase default timeouts for potentially slower E2E interactions
    timeout = httpx.Timeout(10.0, connect=5.0, read=30.0, write=10.0)

    async with httpx.AsyncClient(base_url=proxy_target_url_file_based, headers=headers, timeout=timeout) as client:
        # Optional: Perform a quick health check before yielding
        try:
            health_response = await client.get("/health")
            health_response.raise_for_status()  # Raise exception for 4xx/5xx status codes
            print(f"Successfully connected to health endpoint at {proxy_target_url_file_based}/health")
        except httpx.RequestError as exc:
            pytest.fail(
                f"Failed to connect to target proxy health endpoint {proxy_target_url_file_based}/health: {exc}"
            )
        except httpx.HTTPStatusError as exc:
            pytest.fail(
                f"Target proxy health endpoint {proxy_target_url_file_based}/health returned "
                f"error status {exc.response.status_code}: {exc.response.text}"
            )

        yield client
        # httpx.AsyncClient is automatically closed by the async context manager
        print(f"\nClosed httpx client for {proxy_target_url_file_based}")


@pytest_asyncio.fixture(scope="function")
async def e2e_client_db_based(
    proxy_target_url_db_based: str, client_api_key: str
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Provides an httpx.AsyncClient configured to talk to the database-based policy proxy.
    """
    headers = {
        "Authorization": f"Bearer {client_api_key}",
        "Accept": "application/json",
    }
    # Increase default timeouts for potentially slower E2E interactions
    timeout = httpx.Timeout(10.0, connect=5.0, read=30.0, write=10.0)

    async with httpx.AsyncClient(base_url=proxy_target_url_db_based, headers=headers, timeout=timeout) as client:
        # Optional: Perform a quick health check before yielding
        try:
            health_response = await client.get("/health")
            health_response.raise_for_status()  # Raise exception for 4xx/5xx status codes
            print(f"Successfully connected to health endpoint at {proxy_target_url_db_based}/health")
        except httpx.RequestError as exc:
            pytest.fail(f"Failed to connect to target proxy health endpoint {proxy_target_url_db_based}/health: {exc}")
        except httpx.HTTPStatusError as exc:
            pytest.fail(
                f"Target proxy health endpoint {proxy_target_url_db_based}/health returned "
                f"error status {exc.response.status_code}: {exc.response.text}"
            )

        yield client
        # httpx.AsyncClient is automatically closed by the async context manager
        print(f"\nClosed httpx client for {proxy_target_url_db_based}")
