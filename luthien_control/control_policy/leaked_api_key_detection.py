"""
Control Policy for detecting leaked API keys in LLM message content.

This policy inspects the 'messages' field in request bodies to prevent
sensitive API keys from being sent to language models.
"""

import json
import logging
import re
from typing import List, Optional, Pattern, cast

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import LeakedApiKeyError, NoRequestError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.tracked_context import TrackedContext

from .serialization import SerializableDict


class LeakedApiKeyDetectionPolicy(ControlPolicy):
    """Detects API keys that might be leaked in message content sent to LLMs."""

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
        self.name = name or self.__class__.__name__
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.compiled_patterns: List[Pattern] = [re.compile(pattern) for pattern in self.patterns]
        self.logger = logging.getLogger(__name__)

    async def apply(
        self,
        context: TrackedContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TrackedContext:
        """
        Checks message content for potentially leaked API keys.

        Args:
            context: The current transaction context.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession.

        Returns:
            The transaction context, potentially with an error response set.

        Raises:
            NoRequestError: If the request is not found in the context.
            LeakedApiKeyError: If a potential API key is detected in message content.
        """
        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context.")

        self.logger.info(f"[{context.transaction_id}] Checking for leaked API keys in message content ({self.name}).")

        # Only look at POST requests with content
        if not context.request.content:
            self.logger.debug(f"[{context.transaction_id}] No content to check for API keys.")
            return context

        try:
            # Get the request body as JSON
            body_json = json.loads(context.request.content)

            # Check the "messages" field for leaked API keys
            if "messages" in body_json and isinstance(body_json["messages"], list):
                messages = body_json["messages"]

                # Inspect each message's content
                for message in messages:
                    if "content" in message and isinstance(message["content"], str):
                        content = message["content"]
                        if self._check_text(content):
                            error_message = (
                                "Potential API key detected in message content. "
                                "For security, the request has been blocked."
                            )
                            self.logger.warning(f"[{context.transaction_id}] {error_message} ({self.name})")

                            context.update_response(
                                status_code=403,
                                headers={"Content-Type": "application/json"},
                                content=json.dumps({"detail": error_message}).encode(),
                            )
                            raise LeakedApiKeyError(detail=error_message)

        except (UnicodeDecodeError, json.JSONDecodeError):
            # If the body isn't valid JSON or text, we can't check it effectively
            self.logger.debug(f"[{context.transaction_id}] Could not decode request body as JSON.")
            pass

        return context

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

    def serialize(self) -> SerializableDict:
        """Serializes the policy's configuration."""
        return cast(
            SerializableDict,
            {
                "name": self.name,
                "patterns": self.patterns,
            },
        )

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
