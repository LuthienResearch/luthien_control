from typing import Any

import pytest
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.core.dependency_container import DependencyContainer
from sqlalchemy.ext.asyncio import AsyncSession


class MinimalConcretePolicy(ControlPolicy):
    """A minimal concrete implementation for testing purposes."""

    name = "minimal_concrete"

    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        # Minimal implementation for testing instantiation
        context.modified_by.append(self.name)
        return context

    def serialize(self) -> SerializableDict:
        # Minimal implementation for testing instantiation
        return {"name": self.name}

    @classmethod
    async def from_serialized(cls, config: SerializableDict, **kwargs: Any) -> "MinimalConcretePolicy":
        # Minimal implementation for testing instantiation
        instance = cls()
        instance.name = config.get("name", cls.name)
        return instance


def test_cannot_instantiate_abc_directly():
    """Verify that ControlPolicy ABC cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class ControlPolicy"):
        ControlPolicy()


def test_subclass_must_implement_abstract_methods():
    """Verify that a subclass missing abstract methods cannot be instantiated."""

    class IncompletePolicy(ControlPolicy):
        name = "incomplete"

        # Missing apply, serialize, from_serialized

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompletePolicy"):
        IncompletePolicy()


def test_can_instantiate_concrete_subclass():
    """Verify that a correctly implemented concrete subclass can be instantiated."""
    try:
        policy = MinimalConcretePolicy()
        assert isinstance(policy, ControlPolicy)
        assert policy.name == "minimal_concrete"
    except TypeError:
        pytest.fail("MinimalConcretePolicy should be instantiable but raised TypeError.")
