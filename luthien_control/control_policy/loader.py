"""Loads control policies from serialized data."""

from typing import TYPE_CHECKING, Dict

# Import the load error exception
from .exceptions import PolicyLoadError

# Import serialization types
from .serialization import SerializableDict

if TYPE_CHECKING:
    # Use forward reference for ControlPolicy to avoid circular import at runtime
    from .control_policy import ControlPolicy


def load_policy(policy_data: Dict[str, SerializableDict], **available_dependencies) -> "ControlPolicy":
    """
    Loads a ControlPolicy instance from a dictionary containing its name and config,
    injecting required dependencies.

    Args:
        policy_data: A dictionary with 'name' (str) and 'config' (SerializableDict).
                     Example: {
                        'name': 'add_api_key_header',
                        'config': {'header_name': 'X-API-Key', 'api_key_env_var': 'BACKEND_API_KEY'}
                    }
        **available_dependencies: Keyword arguments for dependencies potentially needed by policies
                                (e.g., api_key_lookup=ApiKeyLookup(...)).

    Returns:
        An instantiated ControlPolicy object.

    Raises:
        PolicyLoadError: If the policy name is unknown, data is missing/malformed,
                         or a required dependency is not provided.
        Exception: Potentially from the policy's from_serialized method if config is invalid.
    """
    # Import the policy registry here to avoid circular import
    from .registry import POLICY_NAME_TO_CLASS  # noqa: F401

    policy_name = policy_data.get("name")
    policy_config = policy_data.get("config")

    if not isinstance(policy_name, str):
        raise PolicyLoadError(f"Policy 'name' must be a string, got: {type(policy_name)}")
    if not isinstance(policy_config, dict):
        raise PolicyLoadError(f"Policy 'config' must be a dictionary, got: {type(policy_config)}")

    policy_class = POLICY_NAME_TO_CLASS.get(policy_name)
    if policy_class is None:
        raise PolicyLoadError(
            f"Unknown policy name: '{policy_name}'. Available policies: {list(POLICY_NAME_TO_CLASS.keys())}"
        )

    # --- Dependency Injection Logic ---
    required_deps_set = getattr(policy_class, "REQUIRED_DEPENDENCIES", set())
    needed_deps = {}
    missing_deps = []

    for dep_name in required_deps_set:
        if dep_name in available_dependencies:
            needed_deps[dep_name] = available_dependencies[dep_name]
        else:
            missing_deps.append(dep_name)

    if missing_deps:
        raise PolicyLoadError(
            f"Policy '{policy_name}' requires missing dependencies: {', '.join(missing_deps)}. "
            f"Available dependencies: {list(available_dependencies.keys())}"
        )
    # --- End Dependency Injection ---

    # The policy class's from_serialized method handles config validation
    # and now accepts dependencies.
    try:
        # Pass the filtered, necessary dependencies to the policy
        return policy_class.from_serialized(policy_config, **needed_deps)
    except Exception as e:
        # Re-raise potentially informative errors from the policy's constructor
        # Add context about which policy failed.
        raise PolicyLoadError(f"Error loading policy '{policy_name}' with config {policy_config}: {e}") from e
