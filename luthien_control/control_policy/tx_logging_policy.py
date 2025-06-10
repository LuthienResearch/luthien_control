"""Control Policy for logging requests and responses based on TxLoggingSpec instances."""

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging import LuthienLogData, TxLoggingSpec
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.tracked_context import TrackedContext
from luthien_control.db.sqlmodel_models import LuthienLog, NaiveDatetime

logger = logging.getLogger(__name__)


class TxLoggingPolicy(ControlPolicy):
    """A control policy that logs data based on a list of TxLoggingSpec instances."""

    TYPE_NAME = "TxLoggingPolicy"

    def __init__(
        self,
        spec: TxLoggingSpec,
        name: Optional[str] = "TxLoggingPolicy",
        **kwargs: Any,
    ) -> None:
        """Initializes the TxLoggingPolicy.

        Args:
            spec: A TxLoggingSpec instance that defines what to log.
            name: An optional name for the policy instance.
            **kwargs: Additional keyword arguments passed to the superclass.
        """
        super().__init__(**kwargs)
        self.name = name or self.TYPE_NAME
        self.spec = spec

    async def _log_database_entry(
        self,
        session: AsyncSession,
        transaction_id: str,
        log_datetime: NaiveDatetime,
        log_data_obj: LuthienLogData,
    ) -> None:
        """Helper to create and add LuthienLog entry to session from LuthienLogData."""
        log_entry = LuthienLog(
            transaction_id=transaction_id,
            datetime=log_datetime,
            data=log_data_obj.data,
            datatype=log_data_obj.datatype,
            notes=log_data_obj.notes,
        )
        session.add(log_entry)
        await session.commit()
        logger.debug(f"Prepared log entry for {log_data_obj.datatype} (tx: {transaction_id})")

    async def apply(
        self, context: TrackedContext, container: DependencyContainer, session: AsyncSession
    ) -> TrackedContext:
        """Applies all configured logging specifications to the transaction context."""

        current_dt = NaiveDatetime.now()
        tx_id = str(context.transaction_id)

        try:
            log_data_obj = self.spec.generate_log_data(context)
            await self._log_database_entry(session, tx_id, current_dt, log_data_obj)
            logger.info(
                f"Logged data for transaction {tx_id} via spec type {self.spec.TYPE_NAME}, "
                f"datatype {log_data_obj.datatype}"
            )
        except Exception as e:
            logger.error(
                f"Error during logging for transaction {tx_id} with spec "
                f"{getattr(self.spec, 'TYPE_NAME', 'UnknownSpec')} (policy: {self.name}): {e}",
                exc_info=True,
            )
            # Do not re-raise, logging failure should not break the main flow.

        return context

    def serialize(self) -> SerializableDict:
        """Serializes the policy's configuration, including its spec."""
        return SerializableDict(
            {
                "type": self.TYPE_NAME,
                "name": self.name,
                "spec": self.spec.serialize(),
            }
        )

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "TxLoggingPolicy":
        """Creates an instance of TxLoggingPolicy from serialized data.

        This involves deserializing the configured logging spec.
        """
        policy_name = config.get("name", cls.TYPE_NAME)
        if not isinstance(policy_name, (str, type(None))):
            # Fallback to TYPE_NAME if policy_name is not a string or None
            policy_name = cls.TYPE_NAME

        serialized_spec = config.get("spec")

        if not isinstance(serialized_spec, dict):
            raise ValueError("TxLoggingPolicy config missing 'spec' dictionary.")

        try:
            # Use the TxLoggingSpec base class from_serialized as a dispatcher
            spec_instance = TxLoggingSpec.from_serialized(serialized_spec)
        except Exception as e:
            raise ValueError(f"Error deserializing spec (config: {serialized_spec}): {e}") from e

        return cls(name=policy_name, spec=spec_instance)
