import logging
import os
import socket
import subprocess
import sys
import time
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from luthien_control.config.settings import Settings

# Add imports needed for policy creation
# Add new imports for async engine and session management
from luthien_control.db.database_async import (
    close_main_db_engine,
    create_main_db_engine,
    get_main_db_session,
)
from luthien_control.db.sqlmodel_crud import (
    create_policy_config,
    get_policy_config_by_name,
    update_policy_config,
)
from luthien_control.db.sqlmodel_models import Policy

# Load .env file for local development environment variables
# This ensures OPENAI_API_KEY and potentially BACKEND_URL are loaded if defined there
# In CI/deployed envs, these should be set directly as environment variables
load_dotenv()

# Configure logging for the helper function
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)  # Basic config for visibility

E2E_POLICY_NAME = "e2e_test_policy"


async def _ensure_e2e_policy_exists():
    """Connects to DB and ensures the E2E test policy exists and is configured correctly."""
    Settings()
    engine_created = False
    logger.info(f"Ensuring E2E policy '{E2E_POLICY_NAME}' exists in database...")
    try:
        # Use the same env vars the server process will use
        # Create the engine instead of the pool
        engine = await create_main_db_engine()
        if not engine:
            raise RuntimeError("Failed to create main database engine for E2E setup.")
        engine_created = True

        # Use the async session generator
        async for session in get_main_db_session():
            existing_policy = await get_policy_config_by_name(session, E2E_POLICY_NAME)

            # Define the desired state
            desired_class_path = "luthien_control.control_policy.compound_policy.CompoundPolicy"
            desired_config = {
                "policies": [
                    {
                        "name": "E2E_ClientAPIKeyCheck",
                        "policy_class_path": "luthien_control.control_policy.client_api_key_auth.ClientApiKeyAuthPolicy",
                    },
                    {
                        "name": "E2E_AddBackendKey",
                        "policy_class_path": "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy",
                    },
                    {
                        "name": "E2E_ForwardRequest",
                        "policy_class_path": (
                            "luthien_control.control_policy.send_backend_request.SendBackendRequestPolicy"
                        ),
                    },
                ]
            }
            desired_description = "E2E Test Policy: Adds backend key -> Sends request."

            if existing_policy:
                # Check if update is needed
                if (
                    existing_policy.config != desired_config
                    or existing_policy.policy_class_path != desired_class_path
                    or existing_policy.description != desired_description
                    or not existing_policy.is_active  # Ensure it's active
                ):
                    logger.info(f"Policy '{E2E_POLICY_NAME}' (ID: {existing_policy.id}) exists but needs update.")
                    update_data = Policy(
                        id=existing_policy.id,
                        name=existing_policy.name,
                        policy_class_path=desired_class_path,
                        config=desired_config,
                        is_active=True,
                        description=desired_description,
                        created_at=existing_policy.created_at,
                    )
                    updated_policy = await update_policy_config(session, existing_policy.id, update_data)
                    if updated_policy:
                        logger.info(f"Successfully updated policy '{E2E_POLICY_NAME}'.")
                    else:
                        logger.error(f"Failed to update policy '{E2E_POLICY_NAME}'.")
                        # Optionally raise an error to fail the test setup
                        raise RuntimeError(f"Failed to update E2E policy '{E2E_POLICY_NAME}'")
                else:
                    logger.info(f"Policy '{E2E_POLICY_NAME}' exists and is up-to-date.")
            else:
                logger.info(f"Policy '{E2E_POLICY_NAME}' not found. Creating...")
                e2e_policy_data = Policy(
                    name=E2E_POLICY_NAME,
                    policy_class_path=desired_class_path,
                    config=desired_config,
                    is_active=True,
                    description=desired_description,
                )
                created_policy = await create_policy_config(session, e2e_policy_data)
                if created_policy:
                    logger.info(f"Successfully created policy '{E2E_POLICY_NAME}' (ID: {created_policy.id}).")
                else:
                    logger.error(f"Failed to create policy '{E2E_POLICY_NAME}'.")
                    # Optionally raise an error to fail the test setup
                    raise RuntimeError(f"Failed to create E2E policy '{E2E_POLICY_NAME}'")

    except Exception as e:
        logger.exception(f"Error ensuring E2E policy exists: {e}")
        raise  # Re-raise to fail the test setup
    finally:
        # Close the engine if it was created
        if engine_created:
            await close_main_db_engine()
            logger.info("Closed temporary DB engine used for E2E policy setup.")


# --- Fixtures ---


@pytest.fixture(scope="session")
def openai_api_key() -> str:
    """Fixture to provide the OpenAI API key from environment variables."""
    key = os.getenv("OPENAI_API_KEY")
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
    base_url = f"http://{host}:{port}"

    # Ensure the necessary policy exists in the DB before starting server
    await _ensure_e2e_policy_exists()

    # Prepare environment variables for the subprocess
    server_env = os.environ.copy()
    # Explicitly set required env vars for the E2E server,
    # overriding any potentially inherited values from .env.test
    server_env["OPENAI_API_KEY"] = openai_api_key
    # Default to real OpenAI backend for E2E tests unless overridden by system env
    server_env["BACKEND_URL"] = os.environ.get("BACKEND_URL", "https://api.openai.com/v1")
    # Tell the server process to load the specific policy created for E2E tests
    server_env["TOP_LEVEL_POLICY_NAME"] = "e2e_test_policy"

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
    """Retrieves the client API key from the environment variable."""
    key = os.environ.get("TEST_CLIENT_API_KEY")
    if not key:
        pytest.skip(
            "Skipping E2E tests: TEST_CLIENT_API_KEY environment variable not set. "
            "Set this variable with a valid client key for the target proxy."
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
