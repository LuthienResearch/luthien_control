import logging

import httpx
from fastapi import status
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.tracked_context import TrackedContext
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# --- Dummy Classes for Policy Loading Tests ---


# A valid policy that inherits correctly and takes no args
class DummyPolicyNoArgs(ControlPolicy):
    async def apply(
        self, context: TrackedContext, container: DependencyContainer, session: AsyncSession
    ) -> TrackedContext:
        logger.info(f"[{context.transaction_id}] Running DummyPolicyNoArgs apply")
        context.set_data("policy_no_args_ran", True)
        # Set a success status for testing purposes, as this policy doesn't call a backend
        context.set_data("final_status_code", status.HTTP_200_OK)
        return context

    def serialize(self) -> SerializableDict:
        return {}


# A valid policy requiring settings
class DummyPolicySettings(ControlPolicy):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def apply(
        self, context: TrackedContext, container: DependencyContainer, session: AsyncSession
    ) -> TrackedContext:
        logger.info(f"[{context.transaction_id}] Running DummyPolicySettings apply")
        context.set_data("policy_settings_ran", True)
        context.set_data("settings_value_in_policy", self.settings.get_backend_url())
        # Set a success status for testing purposes
        context.set_data("final_status_code", status.HTTP_200_OK)
        return context

    def serialize(self) -> SerializableDict:
        return {}


# A valid policy requiring http_client
class DummyPolicyHttpClient(ControlPolicy):
    def __init__(self, http_client: httpx.AsyncClient):
        self.client = http_client

    async def apply(
        self, context: TrackedContext, container: DependencyContainer, session: AsyncSession
    ) -> TrackedContext:
        logger.info(f"[{context.transaction_id}] Running DummyPolicyHttpClient apply")
        context.set_data("policy_http_client_ran", True)
        # Set a success status for testing purposes
        context.set_data("final_status_code", status.HTTP_200_OK)
        return context

    def serialize(self) -> SerializableDict:
        return {}


# A valid policy requiring both
class DummyPolicyComplex(ControlPolicy):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self.settings = settings
        self.client = http_client

    async def apply(
        self, context: TrackedContext, container: DependencyContainer, session: AsyncSession
    ) -> TrackedContext:
        logger.info(f"[{context.transaction_id}] Running DummyPolicyComplex apply")
        context.set_data("policy_complex_ran", True)
        # Set a success status for testing purposes
        context.set_data("final_status_code", status.HTTP_200_OK)
        return context

    def serialize(self) -> SerializableDict:
        return {}


# A class that does NOT inherit from ControlPolicy
class InvalidPolicyNotSubclass:
    pass


# A policy that requires a specific arg we won't provide during loading
class DummyPolicyNeedsSpecificArg(ControlPolicy):
    def __init__(self, specific_arg: str):
        self.specific_arg = specific_arg

    async def apply(
        self, context: TrackedContext, container: DependencyContainer, session: AsyncSession
    ) -> TrackedContext:
        # This won't be reached if loading fails, but implement for completeness
        logger.info(f"[{context.transaction_id}] Running DummyPolicyNeedsSpecificArg apply")
        context.set_data("policy_specific_arg_ran", True)
        context.set_data("final_status_code", status.HTTP_200_OK)
        return context

    def serialize(self) -> SerializableDict:
        return {"specific_arg": self.specific_arg}


# A policy whose __init__ raises an exception
class DummyPolicyInitRaises(ControlPolicy):
    def __init__(self):
        raise ValueError("Deliberate init failure")

    async def apply(
        self, context: TrackedContext, container: DependencyContainer, session: AsyncSession
    ) -> TrackedContext:
        # This method will never be called as __init__ fails
        logger.info(f"[{context.transaction_id}] Running DummyPolicyInitRaises apply (should not happen)")
        return context

    def serialize(self) -> SerializableDict:
        return {}
