import logging
import importlib  # Added for dynamic loading
import inspect  # Added for signature inspection
from typing import Sequence, Type  # Added Type for class checking

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

# Import Settings and the policy loader
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.core.response_builder.interface import ResponseBuilder


# --- Added for API Key Auth --- #
from luthien_control.db.crud import get_api_key_by_value
from luthien_control.db.models import ApiKey

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)  # Use Authorization header
# --- End Added --- #

logger = logging.getLogger(__name__)


# --- Define Error Class locally --- #
class PolicyLoadError(Exception):
    """Custom exception for errors during policy loading."""

    pass


# --- Define Policy Loading Logic locally --- #
def load_control_policies(settings: Settings, http_client: httpx.AsyncClient) -> Sequence[ControlPolicy]:
    """
    Loads and instantiates control policies based on the CONTROL_POLICIES setting.
    Injects dependencies like settings and http_client based on policy __init__ signature.

    Args:
        settings: The application settings instance.
        http_client: The shared httpx client instance.

    Returns:
        A sequence of instantiated ControlPolicy objects.

    Raises:
        PolicyLoadError: If a policy cannot be loaded or instantiated.
    """
    policies_str = settings.get_control_policies_list()
    if not policies_str:
        logger.info("No CONTROL_POLICIES configured, returning empty list.")
        return []

    policy_paths = [path.strip() for path in policies_str.split(",") if path.strip()]
    loaded_policies = []

    for policy_path in policy_paths:
        try:
            module_path, class_name = policy_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            policy_class: Type[ControlPolicy] = getattr(module, class_name)

            # Basic check: Does it implement the ControlPolicy protocol?
            # Note: isinstance check might fail if Protocol isn't runtime_checkable
            # or if the class doesn't explicitly inherit. Checking attribute is safer.
            if not issubclass(policy_class, ControlPolicy):
                raise PolicyLoadError(
                    f"Class '{class_name}' from '{module_path}' does not inherit from ControlPolicy (or is not a recognized subclass)."
                )

            # --- Dependency Injection based on __init__ signature --- #
            sig = inspect.signature(policy_class.__init__)
            init_params = sig.parameters
            instance_args = {}

            if "settings" in init_params:
                instance_args["settings"] = settings
            if "http_client" in init_params:
                instance_args["http_client"] = http_client
            # Add other common dependencies here if needed in the future

            try:
                instance = policy_class(**instance_args)
            except TypeError as e:
                # This might happen if __init__ takes unexpected args or has required args not provided.
                logger.error(f"TypeError instantiating {class_name} with args {instance_args}: {e}")
                # Try without arguments as a fallback ONLY if no specific args were detected
                if not instance_args:
                    logger.warning(f"Attempting to instantiate {class_name} without arguments as fallback.")
                    try:
                        instance = policy_class()
                    except TypeError as fallback_e:
                        logger.error(f"Fallback instantiation of {class_name} failed: {fallback_e}")
                        raise PolicyLoadError(
                            f"Could not instantiate policy class '{class_name}'. Check __init__ signature."
                        ) from fallback_e
                else:
                    raise PolicyLoadError(
                        f"Could not instantiate policy class '{class_name}' with detected args {list(instance_args.keys())}. Check __init__ signature."
                    ) from e
            # --- End Dependency Injection --- #

            loaded_policies.append(instance)
            logger.info(f"Successfully loaded and instantiated control policy: {policy_path}")

        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to import or find class for policy '{policy_path}': {e}")
            raise PolicyLoadError(
                f"Could not load policy class '{policy_path}'. Check path and ensure class exists."
            ) from e
        except PolicyLoadError:  # Re-raise specific PolicyLoadErrors
            raise
        except Exception as e:
            logger.exception(f"Unexpected error loading policy '{policy_path}'")
            raise PolicyLoadError(f"Unexpected error loading policy '{policy_path}': {e}") from e

    return loaded_policies


# --- Dependency Providers --- #


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
        logger.critical("!!! CRITICAL ERROR: httpx.AsyncClient not found in request.app.state")
        raise HTTPException(status_code=500, detail="Internal server error: HTTP client not available.")
    return client


# Global variable to cache the loaded policy instance
# Initialize to None. It will be loaded on first request.



# --- API Key Authentication Dependency ---


async def get_current_active_api_key(api_key: str = Depends(api_key_header)) -> ApiKey:
    """
    Dependency to validate the API key provided in the 'Authorization' header.

    Args:
        api_key: The API key string extracted from the header.

    Returns:
        The validated ApiKey object from the database.

    Raises:
        HTTPException: 401 Unauthorized if the key is missing, invalid, or inactive.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Missing API key.",
            headers={"WWW-Authenticate": "Bearer"},  # Standard practice
        )

    # Strip "Bearer " prefix if present
    if api_key.startswith("Bearer "):
        api_key = api_key[len("Bearer ") :]

    db_key = await get_api_key_by_value(api_key)
    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not db_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Optionally log key usage or perform other checks here
    # logger.info(f"API key validated: {db_key.name} (ID: {db_key.id})")

    return db_key


# --- NEW Control Policy Framework Dependencies ---


def get_initial_context_policy() -> InitializeContextPolicy:
    """Provides an instance of the InitializeContextPolicy."""
    return InitializeContextPolicy()


def get_control_policies(
    settings: Settings = Depends(Settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),  # Inject http_client here
) -> Sequence[ControlPolicy]:
    """
    Dependency to load and provide the sequence of configured ControlPolicy instances.
    Injects http_client dependency into the loader.
    """
    try:
        # Pass injected dependencies to the local loader function
        return load_control_policies(settings=settings, http_client=http_client)
    except PolicyLoadError as e:
        logger.exception(f"Failed to load control policies: {e}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: Could not load configured control policies. {e}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error loading control policies: {e}")
        raise HTTPException(status_code=500, detail="Internal server error: Unexpected issue loading control policies.")


def get_response_builder() -> ResponseBuilder:
    """Provides an instance of the DefaultResponseBuilder."""
    return DefaultResponseBuilder()
