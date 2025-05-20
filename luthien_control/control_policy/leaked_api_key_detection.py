"""
Control Policy for detecting leaked API keys in LLM message content.

This policy inspects the 'messages' field in request bodies to prevent
sensitive API keys from being sent to language models.
"""

import json
import logging
import re
from typing import List, Optional, Pattern, cast

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import LeakedApiKeyError, NoRequestError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext

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
        context: TransactionContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TransactionContext:
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
        if not hasattr(context.request, "content") or not context.request.content:
            self.logger.debug(f"[{context.transaction_id}] No content to check for API keys.")
            return context

        try:
            # Get the request body as JSON
            body_content = context.request.content.decode("utf-8")
            body_json = json.loads(body_content)

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

                            context.response = httpx.Response(
                                status_code=403,
                                json={"detail": error_message},
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
        """
        name_val = config.get("name")
        resolved_name: Optional[str] = None
        if name_val is not None:
            if not isinstance(name_val, str):
                logging.warning(
                    f"LeakedApiKeyDetectionPolicy name '{name_val}' from config is not a string. "
                    f"Coercing. Original type: {type(name_val).__name__}."
                )
                resolved_name = str(name_val)
            else:
                resolved_name = name_val

        patterns_val = config.get("patterns")
        resolved_patterns: Optional[List[str]] = None
        if patterns_val is not None:
            if not isinstance(patterns_val, list):
                raise TypeError(
                    f"LeakedApiKeyDetectionPolicy 'patterns' in config must be a list of strings. "
                    f"Got: {patterns_val!r} (type: {type(patterns_val).__name__})"
                )
            # Ensure all elements in the list are strings
            if not all(isinstance(p, str) for p in patterns_val):
                # Find the first non-string element for a better error message
                offending_item = next((p for p in patterns_val if not isinstance(p, str)), None)
                raise TypeError(
                    f"All items in the 'patterns' list for LeakedApiKeyDetectionPolicy must be strings. "
                    f"Found item: {offending_item!r} (type: {type(offending_item).__name__}) in list: {patterns_val!r}"
                )
            resolved_patterns = patterns_val  # Now known to be List[str]

        return cls(
            name=resolved_name,
            patterns=resolved_patterns,
        )
