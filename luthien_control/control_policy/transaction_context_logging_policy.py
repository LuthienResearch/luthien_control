import json
import logging
import re
from typing import Any, Dict, Optional, TypeVar, cast

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction

T = TypeVar("T")


class TransactionContextLoggingPolicy(ControlPolicy):
    """A policy that logs transaction context with sensitive data redacted.

    This policy logs the current transaction context to help with debugging
    and monitoring. Sensitive data like API keys, authorization headers,
    and passwords are automatically redacted for security.

    Attributes:
        name (str): The name of this policy instance.
        log_level (str): The logging level to use (DEBUG, INFO, WARNING, ERROR).
    """

    name: Optional[str] = Field(default="TransactionContextLoggingPolicy")
    log_level: str = Field(default="INFO")

    def __init__(self, **data: dict | list | str) -> None:
        super().__init__(**data)
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    def _redact_sensitive_data(self, data: T) -> T:
        """Recursively redact sensitive data from a data structure.

        Args:
            data: The data to redact (dict, list, str, or other types)

        Returns:
            The data with sensitive values redacted
        """
        if isinstance(data, dict):
            return cast(T, {key: self._redact_value(key, value) for key, value in data.items()})
        elif isinstance(data, list):
            return cast(T, [self._redact_sensitive_data(item) for item in data])
        else:
            return cast(T, self._redact_value("", data))

    def _redact_value(self, key: str, value: Any) -> Any:
        """Redact a single value if the key indicates it contains sensitive data.

        Args:
            key: The field name
            value: The field value

        Returns:
            The original value or a redacted version
        """
        if not isinstance(value, (str, dict, list)):
            return value

        # List of field names that typically contain sensitive data
        sensitive_keys = {
            "api_key",
            "apikey",
            "api-key",
            "password",
            "passwd",
            "pwd",
            "secret",
            "token",
            "auth",
            "authorization",
            "bearer",
            "key",
            "private_key",
            "secret_key",
            "client_secret",
            "client_id",
        }

        # First check for authorization header patterns
        if isinstance(value, str):
            # Redact Bearer tokens
            bearer_pattern = r"(Bearer\s+)([A-Za-z0-9\-_.]+)"
            bearer_result = re.sub(bearer_pattern, r"\1***", value, flags=re.IGNORECASE)
            if bearer_result != value:
                return bearer_result

        key_lower = key.lower().replace("-", "_")

        if key_lower in sensitive_keys:
            if isinstance(value, str):
                if len(value) == 0:
                    return ""  # Empty strings remain empty
                elif len(value) > 8:
                    # Show first 4 chars, then *** for the rest
                    return f"{value[:4]}***"
                else:
                    return "***"
            else:
                return self._redact_sensitive_data(value)

        # Check for API key patterns if not already handled
        if isinstance(value, str):
            # Redact API key patterns (specific formats only)
            api_key_patterns = [
                r"(sk-[A-Za-z0-9]{20,})",  # OpenAI style
            ]
            for pattern in api_key_patterns:
                if re.match(pattern, value):
                    return f"{value[:4]}***" if len(value) > 8 else "***"

        # Recursively handle nested structures
        if isinstance(value, (dict, list)):
            return self._redact_sensitive_data(value)

        return value

    def _safe_model_dump(self, obj: Any) -> Dict[str, Any]:
        """Safely convert an object to a dictionary, handling objects without model_dump.

        Args:
            obj: The object to serialize

        Returns:
            A dictionary representation of the object
        """
        if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
            try:
                return obj.model_dump(mode="python")
            except Exception as e:
                # Fall back to string representation if model_dump fails
                return {"_serialization_error": f"model_dump failed: {e}", "_str_repr": str(obj)}
        elif hasattr(obj, "__dict__"):
            # For objects with __dict__, try to convert to dict
            try:
                result = {}
                for k, v in obj.__dict__.items():
                    if not k.startswith("_"):
                        try:
                            # Some attributes might be properties that raise exceptions when accessed
                            # So we serialize the value safely too
                            if hasattr(v, "__call__") and not hasattr(v, "__dict__"):
                                # Skip callable objects that aren't classes
                                result[k] = f"<callable: {type(v).__name__}>"
                            else:
                                result[k] = v
                        except Exception as e:
                            result[k] = f"<access_error: {e}>"
                return result
            except Exception:
                return {"_str_repr": str(obj)}
        else:
            # For other objects, just convert to string
            return {"_str_repr": str(obj)}

    def _serialize_transaction_context(self, transaction: Transaction) -> Dict[str, Any]:
        """Serialize transaction to a loggable format with redaction.

        Args:
            transaction: The transaction to serialize

        Returns:
            A dictionary representation of the transaction context
        """
        context = {
            "transaction_id": str(transaction.transaction_id),
            "request_type": transaction.request_type.value if transaction.request_type else None,
        }

        # Add OpenAI request data if present
        if transaction.openai_request:
            openai_data = self._safe_model_dump(transaction.openai_request)
            context["openai_request"] = self._redact_sensitive_data(openai_data)

        # Add raw request data if present
        if transaction.raw_request:
            raw_data = self._safe_model_dump(transaction.raw_request)
            context["raw_request"] = self._redact_sensitive_data(raw_data)

        # Add OpenAI response data if present (typically not sensitive, but check anyway)
        if transaction.openai_response:
            response_data = self._safe_model_dump(transaction.openai_response)
            context["openai_response"] = self._redact_sensitive_data(response_data)

        # Add raw response data if present
        if transaction.raw_response:
            raw_response_data = self._safe_model_dump(transaction.raw_response)
            context["raw_response"] = self._redact_sensitive_data(raw_response_data)

        # Add transaction data (custom fields)
        if transaction.data:
            context["transaction_data"] = self._redact_sensitive_data(dict(transaction.data))

        return context

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """Log the transaction context with sensitive data redacted.

        Args:
            transaction: The current transaction
            container: The dependency injection container
            session: The database session

        Returns:
            The unmodified transaction (this policy only logs)
        """
        try:
            context = self._serialize_transaction_context(transaction)

            # Log JSON version for easy copy-paste into JSON analysis tools
            log_level = getattr(logging, self.log_level.upper(), logging.INFO)
            context_json = json.dumps(context, indent=2, default=str)
            self.logger.log(log_level, f"Transaction Context JSON:\n{context_json}")

        except Exception as e:
            # Don't let logging errors break the transaction flow
            self.logger.error(f"Failed to log transaction context: {e}")

        return transaction
