import logging
from typing import Sequence

import httpx
from fastapi import Depends, HTTPException, Request

# Import Settings and the policy loader
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.policies.base import Policy
from luthien_control.policy_loader import PolicyLoadError, load_control_policies, load_policy


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
