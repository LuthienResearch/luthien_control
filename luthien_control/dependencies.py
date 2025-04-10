import importlib  # Added for dynamic loading
import inspect  # Added for signature inspection
import logging
from typing import Sequence, Type

import httpx
from fastapi import Depends, HTTPException, Request

# Import Settings and the policy loader
from luthien_control.config.settings import Settings

# Import Policies
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy

# Import Response Builder
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.core.response_builder.interface import ResponseBuilder

# Import DB access function (now needed for policy instantiation)
from luthien_control.db.crud import get_api_key_by_value

logger = logging.getLogger(__name__)


# Reinstate local PolicyLoadError
class PolicyLoadError(Exception):
    """Custom exception for errors during policy loading."""

    pass


# Reinstate original environment variable loader
def load_control_policies(settings: Settings, http_client: httpx.AsyncClient) -> Sequence[ControlPolicy]:
    """
    Loads and instantiates control policies based on the CONTROL_POLICIES setting.
    Injects dependencies like settings, http_client, and api_key_lookup based on policy __init__ signature.

    Args:
        settings: The application settings instance.
        http_client: The shared httpx client instance.

    Returns:
        A sequence of instantiated ControlPolicy objects.

    Raises:
        PolicyLoadError: If a policy cannot be loaded or instantiated.
    """
    # Use the appropriate getter from Settings (assuming it will be reverted too)
    policies_str = settings.get_control_policies_list()
    if not policies_str:
        logger.info("No CONTROL_POLICIES configured in settings, returning empty list.")
        policy_paths = []
    else:
        policy_paths = [path.strip() for path in policies_str.split(",") if path.strip()]

    loaded_policies = []

    for policy_path in policy_paths:
        try:
            module_path, class_name = policy_path.rsplit(".", 1)

            module = importlib.import_module(module_path)
            policy_class: Type[ControlPolicy] = getattr(module, class_name)

            if not issubclass(policy_class, ControlPolicy):
                raise PolicyLoadError(
                    f"Class '{class_name}' from '{module_path}' does not inherit from "
                    f"ControlPolicy (or is not a recognized subclass)."
                )

            # --- Dependency Injection based on __init__ signature --- #
            sig = inspect.signature(policy_class.__init__)
            init_params = sig.parameters
            instance_args = {}

            if "settings" in init_params:
                instance_args["settings"] = settings
            if "http_client" in init_params:
                instance_args["http_client"] = http_client
            if "api_key_lookup" in init_params:
                # Ensure get_api_key_by_value is correctly imported and used
                instance_args["api_key_lookup"] = get_api_key_by_value
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
                        f"Could not instantiate policy class '{class_name}' with detected args "
                        f"{list(instance_args.keys())}. Check __init__ signature."
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


# --- NEW Control Policy Framework Dependencies ---


def get_initial_context_policy() -> InitializeContextPolicy:
    """Provides an instance of the InitializeContextPolicy."""
    return InitializeContextPolicy()


# Revert to original get_control_policies returning sequence
def get_control_policies(
    settings: Settings = Depends(Settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),  # Inject http_client here
    # api_key_lookup is now injected inside load_control_policies
) -> Sequence[ControlPolicy]:  # Return Sequence again
    """
    Dependency to load and provide the sequence of configured ControlPolicy instances.
    Injects http_client dependency into the loader.
    Uses CONTROL_POLICIES environment variable.
    """
    try:
        # Pass injected dependencies to the reinstated local loader function
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
