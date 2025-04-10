import logging
from typing import Sequence

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

# Import Settings and the policy loader
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.policies.base import Policy
from luthien_control.policy_loader import PolicyLoadError, load_control_policies, load_policy

# --- Added for API Key Auth --- #
from luthien_control.db.crud import get_api_key_by_value
from luthien_control.db.models import ApiKey

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)  # Use Authorization header
# --- End Added --- #


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


# === New Dependency Providers for Control Policy Framework ===


logger = logging.getLogger(__name__)


# --- API Key Authentication Dependency --- #
async def get_current_active_api_key(
    authorization: str | None = Depends(api_key_header),
) -> ApiKey:
    """
    Dependency to validate the API key provided in the 'Authorization: Bearer <key>' header.

    Raises:
        HTTPException 401: If the header is missing or malformed.
        HTTPException 403: If the key is not found or is inactive.
        HTTPException 503: If the database connection is unavailable.
    """
    if authorization is None:
        logger.debug("Authorization header missing.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},  # Standard hint for Bearer auth
        )

    # Expecting "Bearer <key>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.debug(f"Malformed Authorization header: {authorization}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials: Malformed header",
            headers={"WWW-Authenticate": "Bearer"},  # Standard hint for Bearer auth
        )

    api_key_value = parts[1]
    if not api_key_value:
        logger.debug("Empty token provided in Authorization header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials: Empty token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        api_key_db = await get_api_key_by_value(api_key_value)
    except Exception as e:
        # This might happen if the DB pool isn't initialized or there's a connection error.
        # get_api_key_by_value already logs the specifics.
        logger.error(f"Database error during API key validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable due to database issue.",
        )

    if api_key_db is None:
        logger.warning(f"Invalid API key provided: {api_key_value[:4]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication credentials: Unknown API Key"
        )

    if not api_key_db.is_active:
        logger.warning(f"Inactive API key provided: {api_key_value[:4]}... (Name: {api_key_db.name})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication credentials: API Key is inactive"
        )

    logger.info(f"Successfully authenticated API key: {api_key_db.name} (ID: {api_key_db.id})")
    return api_key_db


# --- End API Key Authentication Dependency --- #


def get_initial_context_policy() -> InitializeContextPolicy:
    """Dependency provider for the InitializeContextPolicy."""
    # Settings could potentially be injected here if needed for initialization
    # settings: Settings = Depends(Settings)
    return InitializeContextPolicy()


def get_control_policies(
    settings: Settings = Depends(Settings), client: httpx.AsyncClient = Depends(get_http_client)
) -> Sequence[ControlPolicy]:
    """Dependency provider for the main sequence of ControlPolicies."""
    try:
        policies = load_control_policies(settings=settings, http_client=client)
        logger.info(f"Loaded {len(policies)} control policies from settings.")
        return policies
    except PolicyLoadError as e:
        logger.exception(
            "Failed to load control policies from settings", extra={"settings_var": settings.CONTROL_POLICIES}
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: Could not load control policies. {e}")
    except Exception:
        logger.exception("Unexpected error loading control policies")
        raise HTTPException(status_code=500, detail="Internal server error: Unexpected issue loading control policies.")


def get_response_builder() -> ResponseBuilder:
    """Dependency provider for the ResponseBuilder."""
    # For now, instantiate the default implementation.
    # Future: Could load based on config.
    return DefaultResponseBuilder()


# === End New Dependency Providers ===
