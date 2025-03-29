"""
Example control policy that counts tokens in requests and responses.
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx
import tiktoken
from fastapi import Request

from ..base import ControlPolicy


class TokenCounterPolicy(ControlPolicy):
    """
    A control policy that counts tokens in requests and responses.

    This is useful for monitoring token usage for cost tracking and rate limiting.
    """

    def __init__(self, model: str = "gpt-3.5-turbo"):
        """
        Initialize the token counter.

        Args:
            model: The model to use for token counting
        """
        self.model = model
        self.encoding = tiktoken.encoding_for_model(model)
        self.counts = {"requests": 0, "responses": 0, "total": 0}

    def _count_tokens_in_messages(self, messages):
        """Count tokens in a messages array for chat completions."""
        num_tokens = 0
        for message in messages:
            num_tokens += 4
            for key, value in message.items():
                num_tokens += len(self.encoding.encode(str(value)))
                if key == "name":
                    num_tokens -= 1
        num_tokens += 2
        return num_tokens

    async def process_request(
        self, request: Request, target_url: str, headers: Dict[str, str], body: Optional[bytes]
    ) -> Dict[str, Any]:
        """Process a request to count tokens."""
        token_count = 0

        if body and "chat/completions" in target_url:
            try:
                data = json.loads(body)
                if "messages" in data:
                    token_count = self._count_tokens_in_messages(data["messages"])
                    self.counts["requests"] += token_count
                    self.counts["total"] += token_count
                    headers["X-Request-Token-Count"] = str(token_count)
            except Exception as e:
                logging.error(f"Error processing request tokens: {e}")
                pass

        return {"target_url": target_url, "headers": headers, "body": body}

    async def process_response(self, request: Request, response: httpx.Response, content: bytes) -> Dict[str, Any]:
        """Process a response to count tokens."""
        token_count = 0

        if content and "chat/completions" in response.url.path:
            try:
                data = json.loads(content)

                if "choices" in data and data["choices"]:
                    message = data["choices"][0].get("message", {})
                    if "content" in message:
                        token_count = len(self.encoding.encode(message["content"]))
                        self.counts["responses"] += token_count
                        self.counts["total"] += token_count
                        response_headers = dict(response.headers)
                        response_headers["X-Response-Token-Count"] = str(token_count)
                        return {"status_code": response.status_code, "headers": response_headers, "content": content}

            except Exception as e:
                logging.error(f"Error processing response tokens: {e}")
                pass

        return {"status_code": response.status_code, "headers": dict(response.headers), "content": content}

    def get_token_counts(self):
        """Get the current token counts."""
        return self.counts
