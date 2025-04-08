import httpx
from fastapi import HTTPException, Request

# Import Settings and the policy loader
from luthien_control.config.settings import Settings
from luthien_control.policies.base import Policy
from luthien_control.policy_loader import PolicyLoadError, load_policy


def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Dependency function to get the shared httpx.AsyncClient from application state.

    Raises:
        HTTPException: If the client is not found in the application state.
    """
    client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if client is None:
        # This indicates a critical setup error if the lifespan manager didn't run
        # or didn't set the state correctly.
        print("!!! CRITICAL ERROR: httpx.AsyncClient not found in request.app.state")
        raise HTTPException(status_code=500, detail="Internal server error: HTTP client not available.")
    return client


# Global variable to cache the loaded policy instance
# Initialize to None. It will be loaded on first request.
_cached_policy: Policy | None = None


def get_policy(request: Request) -> Policy:
    """
    Dependency function to load and provide the configured policy instance.
    Caches the loaded policy in app state to avoid reloading on each request.

    Args:
        request: The FastAPI request object.

    Returns:
        The loaded policy instance.

    Raises:
        HTTPException: If there's an error loading the policy.
    """
    global _cached_policy

    # Check cache first
    if _cached_policy is not None:
        return _cached_policy

    # Instantiate Settings directly to read the policy module name.
    settings = Settings()

    # Load policy if not cached
    try:
        policy_instance = load_policy(settings)
        # Store in cache
        _cached_policy = policy_instance
        return policy_instance
    except PolicyLoadError as e:
        print(f"!!! CRITICAL ERROR: Failed to load policy: {e}")
        # Log the detailed error from the loader
        # In a real app, consider more robust error handling/reporting
        raise HTTPException(status_code=500, detail=f"Internal server error: Could not load configured policy. {e}")
    except Exception as e:
        # Catch any other unexpected errors during loading
        print(f"!!! CRITICAL UNEXPECTED ERROR during policy load: {e}")
        raise HTTPException(status_code=500, detail="Internal server error: Unexpected issue loading policy.")
