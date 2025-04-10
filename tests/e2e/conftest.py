import os
import socket
import subprocess
import sys
import time
from typing import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Load .env file for local development environment variables
# This ensures OPENAI_API_KEY and potentially BACKEND_URL are loaded if defined there
# In CI/deployed envs, these should be set directly as environment variables
load_dotenv()

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


@pytest.fixture(scope="function")
def live_local_proxy_server(openai_api_key: str) -> Generator[str, None, None]:
    """
    Starts a local instance of the FastAPI proxy server in a subprocess
    for function-scoped E2E tests.

    Yields:
        The base URL (http://127.0.0.1:PORT) of the running local server.
    """
    port = _find_free_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"

    # Prepare environment variables for the subprocess
    server_env = os.environ.copy()
    # Explicitly set required env vars for the E2E server,
    # overriding any potentially inherited values from .env.test
    server_env["OPENAI_API_KEY"] = openai_api_key
    # Default to real OpenAI backend for E2E tests unless overridden by system env
    server_env["BACKEND_URL"] = os.environ.get("BACKEND_URL", "https://api.openai.com/v1")
    # Ensure policy is default (NoOp) unless overridden by system env
    server_env["POLICY_MODULE"] = os.environ.get("POLICY_MODULE", "luthien_control.policies.examples.no_op.NoOpPolicy")
    # Define default control policies for the beta /beta/ endpoint
    # Needed for the new policy orchestration flow
    default_control_policies = [
        # "luthien_control.control_policy.request_logging.RequestLoggingPolicy", # Temporarily disabled until implemented
        "luthien_control.control_policy.send_backend_request.SendBackendRequestPolicy",
    ]
    # Use comma-separated string for env var
    server_env["CONTROL_POLICIES"] = os.environ.get("CONTROL_POLICIES", ",".join(default_control_policies))

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
    print(f"Local server env POLICY_MODULE: {server_env.get('POLICY_MODULE')}")
    print(f"Local server env CONTROL_POLICIES: {server_env.get('CONTROL_POLICIES')}")
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


@pytest_asyncio.fixture(scope="function")
async def e2e_client(proxy_target_url: str, openai_api_key: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Provides an httpx.AsyncClient configured to talk to the target proxy URL
    with the necessary OpenAI API key authentication header.
    """
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Accept": "application/json",  # Good practice
        # Add any other common headers needed for your tests
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
