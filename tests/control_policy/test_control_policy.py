from typing import Any, cast

import pytest
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from sqlalchemy.ext.asyncio import AsyncSession


class MinimalConcretePolicy(ControlPolicy):
    """A minimal concrete implementation for testing purposes."""

    name = "minimal_concrete"

    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        # Minimal implementation for testing instantiation
        context.data.setdefault("modified_by", []).append(self.name)
        return context

    def serialize(self) -> SerializableDict:
        # Minimal implementation for testing instantiation
        return {"name": self.name}

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs: Any) -> "MinimalConcretePolicy":
        # Minimal implementation for testing instantiation
        instance = cls()
        name_val = config.get("name", cls.name)
        if not isinstance(name_val, str):
            # Fallback or raise error if name is not a string, as per your project's error handling
            # For this example, let's assume it should default or raise if type is wrong.
            # This specific handling might need adjustment based on stricter type requirements.
            if name_val is not None:
                # Attempt to cast or handle non-str cases appropriately if they are valid
                # For now, let's assume if it's not None, it *should* have been a string.
                # A more robust solution might involve raising a TypeError or using a default.
                pass  # Or raise TypeError(f"Expected name to be a string, got {type(name_val)}")
        instance.name = cast(str, name_val) if name_val is not None else cls.name
        return instance


def test_cannot_instantiate_abc_directly():
    """Verify that ControlPolicy ABC cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class ControlPolicy"):
        ControlPolicy()  # type: ignore


def test_subclass_must_implement_abstract_methods():
    """Verify that a subclass missing abstract methods cannot be instantiated."""

    class IncompletePolicy(ControlPolicy):
        name = "incomplete"

        # Missing apply, serialize, from_serialized

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompletePolicy"):
        IncompletePolicy()  # type: ignore


def test_can_instantiate_concrete_subclass():
    """Verify that a correctly implemented concrete subclass can be instantiated."""
    try:
        policy = MinimalConcretePolicy()
        assert isinstance(policy, ControlPolicy)
        assert policy.name == "minimal_concrete"
    except TypeError:
        pytest.fail("MinimalConcretePolicy should be instantiable but raised TypeError.")
