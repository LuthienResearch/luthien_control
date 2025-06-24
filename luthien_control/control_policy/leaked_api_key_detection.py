"""
Control Policy for detecting leaked API keys in LLM message content.

This policy inspects the 'messages' field in request bodies to prevent
sensitive API keys from being sent to language models.
"""

import re
from typing import List, Optional, Pattern, cast

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import LeakedApiKeyError, NoRequestError
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction


class LeakedApiKeyDetectionPolicy(ControlPolicy):
    """Detects API keys that might be leaked in message content sent to LLMs.

    This policy scans message content for patterns matching common API key formats
    to prevent accidental exposure of sensitive credentials to language models.
    """

    # Common API key patterns
    DEFAULT_PATTERNS = [
        r"sk-[a-zA-Z0-9]{48}",  # OpenAI API key pattern
        r"xoxb-[a-zA-Z0-9\-]{50,}",  # Slack bot token pattern
        r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",  # GitHub PAT pattern
    ]

    def __init__(self, patterns: Optional[List[str]] = None, name: Optional[str] = None):
        """Initializes the policy.

        Args:
            patterns: Optional list of regex patterns to detect API keys.
                     If not provided, uses DEFAULT_PATTERNS.
            name: Optional name for this policy instance.
        """
        super().__init__(name=name, patterns=patterns)
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.compiled_patterns: List[Pattern] = [re.compile(pattern) for pattern in self.patterns]

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """
        Checks message content for potentially leaked API keys.

        Args:
            transaction: The current transaction.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession.

        Returns:
            The transaction, potentially with an error response set.

        Raises:
            NoRequestError: If the request is not found in the transaction.
            LeakedApiKeyError: If a potential API key is detected in message content.
        """
        if transaction.request is None:
            raise NoRequestError("No request in transaction.")

        self.logger.info(f"Checking for leaked API keys in message content ({self.name}).")

        if hasattr(transaction.request.payload, "messages"):
            messages = transaction.request.payload.messages

            # Inspect each message's content
            for message in messages:
                if hasattr(message, "content") and isinstance(message.content, str):
                    content = message.content
                    if self._check_text(content):
                        error_message = (
                            "Potential API key detected in message content. For security, the request has been blocked."
                        )
                        self.logger.warning(f"{error_message} ({self.name})")
                        raise LeakedApiKeyError(detail=error_message)

        return transaction

    def _check_text(self, text: str) -> bool:
        """
        Checks if the given text contains any patterns matching potential API keys.

        Args:
            text: The text to check.

        Returns:
            True if a potential API key is found, False otherwise.
        """
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True
        return False

    def _get_policy_specific_config(self) -> SerializableDict:
        """Return policy-specific configuration for serialization.

        This policy needs to store the regex patterns in addition
        to the standard type and name fields.
        """
        return {"patterns": self.patterns}

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "LeakedApiKeyDetectionPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: Dictionary containing configuration options.

        Returns:
            An instance of LeakedApiKeyDetectionPolicy.

        Raises:
            ValueError: If the 'name' or 'patterns' keys are missing or incorrectly typed in the config.
        """
        resolved_name = str(config.get("name", cls.__name__))

        resolved_patterns = cast(List[str], config.get("patterns", cls.DEFAULT_PATTERNS))

        if not isinstance(resolved_patterns, list):
            raise ValueError(
                f"LeakedApiKeyDetectionPolicy 'patterns' must be a list of strings. "
                f"Got: {resolved_patterns!r} (type: {type(resolved_patterns).__name__})"
            )
        if not all(isinstance(p, str) for p in resolved_patterns):
            raise ValueError(
                f"LeakedApiKeyDetectionPolicy 'patterns' must be a list of strings. "
                f"Got: {resolved_patterns!r} (type: {type(resolved_patterns).__name__})"
            )

        return cls(
            name=resolved_name,
            patterns=resolved_patterns,
        )
