import abc
from typing import ClassVar

from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.serialization import SerializableDict


class Condition(abc.ABC):
    """
    Abstract base class for conditions in control policies.

    Conditions are used to evaluate whether a policy should be applied based on
    the current transaction.
    """

    type: ClassVar[str]

    @abc.abstractmethod
    def evaluate(self, transaction: Transaction) -> bool:
        pass

    @abc.abstractmethod
    def serialize(self) -> SerializableDict:
        pass

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
        from luthien_control.new_control_policy.conditions.registry import NAME_TO_CONDITION_CLASS

        condition_type_name_val = serialized.get("type")
        if not isinstance(condition_type_name_val, str):
            # If 'type' is missing (None) or not a string, it's an invalid configuration.
            raise ValueError(
                f"Condition configuration must include a 'type' field as a string. "
                f"Got: {condition_type_name_val!r} (type: {type(condition_type_name_val).__name__})"
            )

        target_condition_class = NAME_TO_CONDITION_CLASS.get(condition_type_name_val)
        if not target_condition_class:
            raise ValueError(
                f"Unknown condition type '{condition_type_name_val}'. "
                f"Ensure it is registered in NAME_TO_CONDITION_CLASS."
            )

        return target_condition_class.from_serialized(serialized)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.serialize()})"

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.serialize() == other.serialize()
