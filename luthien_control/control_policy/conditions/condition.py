import abc

from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext


class Condition(abc.ABC):
    """
    Abstract base class for conditions in control policies.

    Conditions are used to evaluate whether a policy should be applied based on
    the current transaction context.
    """

    type: str

    @abc.abstractmethod
    def evaluate(self, context: TransactionContext) -> bool:
        pass

    @abc.abstractmethod
    def serialize(self) -> SerializableDict:
        pass

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "Condition":
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.serialize()})"

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.serialize() == other.serialize()
