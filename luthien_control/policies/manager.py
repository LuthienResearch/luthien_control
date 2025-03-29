"""
Manager for control policies in the Luthien Control Framework.
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

import httpx
from fastapi import Request

from .base import ControlPolicy


# Define the structure for request data
class RequestData(TypedDict):
    target_url: str
    headers: Dict[str, str]
    body: Optional[bytes]


class PolicyManager:
    """
    Manages the registration and execution of control policies.
    """

    def __init__(self):
        """Initialize an empty list of policies."""
        self._policies: List[ControlPolicy] = []

    def register_policy(self, policy: ControlPolicy) -> None:
        """
        Register a new control policy.

        Args:
            policy: The policy to register
        """
        self._policies.append(policy)

    def unregister_policy(self, policy: ControlPolicy) -> None:
        """
        Unregister a control policy.

        Args:
            policy: The policy to unregister
        """
        if policy in self._policies:
            self._policies.remove(policy)

    async def apply_request_policies(
        self, request: Request, target_url: str, headers: Dict[str, str], body: Optional[bytes]
    ) -> RequestData:
        """
        Apply all request policies in sequence.

        Args:
            request: The original FastAPI request
            target_url: The URL where the request will be sent
            headers: The headers that will be sent
            body: The request body as bytes

        Returns:
            Dict containing potentially modified request components
        """
        # Use the TypedDict for initialization
        request_data: RequestData = {"target_url": target_url, "headers": headers, "body": body}

        for policy in self._policies:
            # Access is now type-checked against RequestData for arguments
            policy_result: Dict[str, Any] = await policy.process_request(
                request, request_data["target_url"], request_data["headers"], request_data["body"]
            )

            # Handle header merging carefully
            policy_headers = policy_result.pop("headers", None)  # Use pop to remove
            if isinstance(policy_headers, dict):
                # Simple update, assumes compatible types from policy for now
                request_data["headers"].update(policy_headers)
            elif policy_headers is not None:
                logging.warning(f"Policy {policy.__class__.__name__} returned non-dict headers: {policy_headers}")

            # Update remaining fields from policy_result
            # This assumes policy_result keys match RequestData structure if they exist
            # More robust checking could be added here if needed
            for key, value in policy_result.items():
                if key in RequestData.__required_keys__ or key in RequestData.__optional_keys__:
                    # Perform basic type check before assigning if possible, or use ignore
                    # This assignment might still cause issues if policy returns wrong type
                    request_data[key] = value  # type: ignore
                else:
                    # If policies can add extra keys, handle them or ignore them
                    pass

        return request_data

    async def apply_response_policies(
        self, request: Request, response: httpx.Response, content: bytes
    ) -> Dict[str, Any]:
        """
        Apply all response policies in sequence.

        Args:
            request: The original FastAPI request
            response: The response from the target API
            content: The response content as bytes

        Returns:
            Dict containing potentially modified response components
        """
        response_data = {"status_code": response.status_code, "headers": dict(response.headers), "content": content}

        for policy in self._policies:
            policy_result = await policy.process_response(request, response, response_data["content"])
            # Merge headers instead of overwriting
            if "headers" in policy_result:
                response_data["headers"] = {**response_data["headers"], **policy_result["headers"]}
                del policy_result["headers"]
            response_data.update(policy_result)

        return response_data
