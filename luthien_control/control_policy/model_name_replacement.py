import json
import logging
from typing import Dict, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import NoRequestError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.tracked_context import TrackedContext

from .serialization import SerializableDict


class ModelNameReplacementPolicy(ControlPolicy):
    """Replaces model names in requests based on a configured mapping.

    This policy allows clients to use fake model names that will be
    replaced with real model names before the request is sent to the backend.
    This is useful for services like Cursor that assume model strings that match
    known models must route through specific endpoints.
    """

    def __init__(self, model_mapping: Dict[str, str], name: Optional[str] = None):
        """Initializes the policy with a mapping of fake to real model names.

        Args:
            model_mapping: Dictionary mapping fake model names to real model names.
            name: Optional name for this policy instance.
        """
        self.model_mapping = model_mapping
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(__name__)

    async def apply(
        self,
        context: TrackedContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TrackedContext:
        """
        Replaces the model name in the request content based on the configured mapping.

        Args:
            context: The current tracked transaction context.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified tracked transaction context.

        Raises:
            NoRequestError: If no request is found in the context.
        """
        # Set current policy for event tracking
        context.set_current_policy(self.name)

        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context.")

        if not context.request.content:
            self.logger.debug(f"[{context.transaction_id}] No content to modify for model name replacement.")
            context.set_current_policy(None)
            return context

        try:
            request_json = context.request.get_json()

            if "model" in request_json:
                original_model = request_json["model"]

                if original_model in self.model_mapping:
                    new_model = self.model_mapping[original_model]
                    self.logger.info(
                        f"[{context.transaction_id}] Replacing model name: {original_model} -> {new_model}"
                    )
                    request_json["model"] = new_model
                    context.request.set_json_content(request_json)

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.warning(f"[{context.transaction_id}] Error processing request content: {e}")

        # Clear current policy
        context.set_current_policy(None)

        return context

    def serialize(self) -> SerializableDict:
        """Serializes the policy configuration."""
        return cast(
            SerializableDict,
            {
                "type": "ModelNameReplacement",
                "name": self.name,
                "model_mapping": self.model_mapping,
            },
        )

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "ModelNameReplacementPolicy":
        """Constructs the policy from serialized configuration."""
        instance_name = cast(str, config.get("name"))
        model_mapping = cast(Dict[str, str], config.get("model_mapping", {}))
        return cls(model_mapping=model_mapping, name=instance_name)
