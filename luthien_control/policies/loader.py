"""Handles loading and instantiation of policy classes based on configuration."""

import importlib
import inspect  # Import inspect module
from typing import List

from luthien_control.config.settings import Settings

# Corrected import path
from luthien_control.policies.base import Policy


class PolicyLoader:
    """Loads policy classes specified in settings."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._request_policy_instances: List[Policy] = []
        self._response_policy_instances: List[Policy] = []
        # TODO: Add caching and potentially reload logic if settings can change

    def load_policies(self):
        """Loads and instantiates policies specified in settings."""
        request_policy_names = self.settings.get_request_policies()
        response_policy_names = self.settings.get_response_policies()

        self._request_policy_instances = self._instantiate_policies(request_policy_names)
        self._response_policy_instances = self._instantiate_policies(response_policy_names)

        print(f"Loaded {len(self._request_policy_instances)} request policies.")
        print(f"Loaded {len(self._response_policy_instances)} response policies.")

    def get_request_policies(self) -> List[Policy]:
        """Returns the loaded request policy instances."""
        # Ensure policies are loaded if not already
        if not self._request_policy_instances:
            self.load_policies()  # Or raise an error if explicit loading is required
        return self._request_policy_instances

    def get_response_policies(self) -> List[Policy]:
        """Returns the loaded response policy instances."""
        if not self._response_policy_instances:
            self.load_policies()
        return self._response_policy_instances

    def _instantiate_policies(self, policy_names: List[str]) -> List[Policy]:
        """Dynamically imports and instantiates concrete policy classes by name."""
        instances = []
        for full_name in policy_names:
            policy_instance = None
            try:
                module_path, class_name = full_name.rsplit(".", 1)
                module = importlib.import_module(module_path)
                policy_class = getattr(module, class_name)

                # --- Validation Checks ---
                if not inspect.isclass(policy_class):
                    print(f"WARNING: Skipping '{full_name}' - not a class.")
                    continue
                if inspect.isabstract(policy_class):
                    print(f"WARNING: Skipping '{full_name}' - is abstract or protocol.")
                    continue
                # Optional: Check if it adheres to Policy protocol (runtime check might be slow)
                # if not issubclass(policy_class, Policy):
                #     print(f"WARNING: Skipping '{full_name}' - does not conform to Policy protocol.")
                #     continue
                # --- End Validation Checks ---

                # Assuming policies don't need constructor args for now
                policy_instance = policy_class()  # type: ignore
                print(f"Successfully instantiated policy: {full_name}")

            except (ImportError, AttributeError, ValueError) as e:
                # Log this error properly
                print(f"ERROR: Failed to load policy '{full_name}': {e}")
                # Decide on error handling: skip, raise, etc. For now, we skip.
                pass
            except Exception as e:
                # Catch other potential instantiation errors
                print(f"ERROR: Failed to instantiate policy '{full_name}': {e}")
                pass

            if policy_instance:
                # Ensure it conforms at runtime (slightly redundant with checks above, but safer)
                if isinstance(policy_instance, Policy):
                    instances.append(policy_instance)
                else:
                    print(
                        f"WARNING: Skipping instance of '{full_name}' - does not conform to Policy protocol at runtime."
                    )

        return instances
