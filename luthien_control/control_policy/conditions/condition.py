import abc
from typing import Any

from pydantic import BaseModel, ConfigDict

from luthien_control.control_policy.serialization import SerializableDict, safe_model_dump, safe_model_validate
from luthien_control.core.transaction import Transaction


class Condition(BaseModel, abc.ABC):
    """
    Abstract base class for conditions in control policies.

    Conditions are used to evaluate whether a policy should be applied based on
    the current transaction.
    """

    type: Any  # Allow any string type including Literal types

    @abc.abstractmethod
    def evaluate(self, transaction: Transaction) -> bool:
        pass

    def serialize(self) -> SerializableDict:
        """Serialize using Pydantic model_dump through SerializableDict validation."""
        data = safe_model_dump(self)
        data["type"] = self.type
        return data

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "Condition":
        """Construct a condition from a serialized configuration.

        This method acts as a dispatcher. It looks up the concrete condition class
        based on the 'type' field in the config and delegates to its from_serialized method.

        Args:
            serialized: The condition-specific configuration dictionary. It must contain
                        a 'type' key that maps to a registered condition type.

        Returns:
            An instance of the concrete condition class.

        Raises:
            ValueError: If the 'type' key is missing in config or the type is not registered.
        """
        # Moved import inside the method to break circular dependency
        from luthien_control.control_policy.conditions.registry import NAME_TO_CONDITION_CLASS

        condition_type_name_val = str(serialized.get("type"))

        target_condition_class = NAME_TO_CONDITION_CLASS[condition_type_name_val]

        return safe_model_validate(target_condition_class, serialized)

    def __repr__(self) -> str:
        return f"{self.serialize()})"

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.serialize() == other.serialize()

    model_config = ConfigDict(arbitrary_types_allowed=True)
