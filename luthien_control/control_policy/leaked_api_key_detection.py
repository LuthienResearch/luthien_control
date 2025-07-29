"""
Control Policy for detecting leaked API keys in LLM message content.

This policy inspects the 'messages' field in request bodies to prevent
sensitive API keys from being sent to language models.
"""

import re
from typing import ClassVar, List, Optional

from pydantic import Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import LeakedApiKeyError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request_type import RequestType
from luthien_control.core.transaction import Transaction


class LeakedApiKeyDetectionPolicy(ControlPolicy):
    """Detects API keys that might be leaked in message content sent to LLMs.

    This policy scans message content for patterns matching common API key formats
    to prevent accidental exposure of sensitive credentials to language models.
    """

    # Common API key patterns
    DEFAULT_PATTERNS: ClassVar[List[str]] = [
        r"sk-[a-zA-Z0-9]{48}",  # OpenAI API key pattern
        r"xoxb-[a-zA-Z0-9\-]{50,}",  # Slack bot token pattern
        r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",  # GitHub PAT pattern
    ]

    name: Optional[str] = Field(default_factory=lambda: "LeakedApiKeyDetectionPolicy")
    patterns: List[str] = Field(default_factory=lambda: LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS)
    compiled_patterns: List[re.Pattern] = Field(default_factory=list, exclude=True)

    @field_validator("patterns", mode="before")
    @classmethod
    def validate_patterns(cls, value):
        """Handle patterns validation and fallback to defaults for empty lists."""
        if value is None or (isinstance(value, list) and not value):
            return cls.DEFAULT_PATTERNS
        return value

    @model_validator(mode="after")
    def compile_patterns(self):
        """Compile regex patterns after validation."""
        self.compiled_patterns = [re.compile(pattern) for pattern in self.patterns]
        return self

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
        # This policy only applies to OpenAI requests
        if transaction.request_type != RequestType.OPENAI_CHAT:
            # No-op for raw requests
            return transaction

        assert transaction.openai_request is not None
        self.logger.info(f"Checking for leaked API keys in message content ({self.name}).")

        if hasattr(transaction.openai_request.payload, "messages"):
            messages = transaction.openai_request.payload.messages

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
