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
        # Initialize current state - Use the RequestData type for clarity
        current_data: RequestData = {"target_url": target_url, "headers": headers.copy(), "body": body}

        for policy in self._policies:
            # Call policy with the current state (passing a copy of headers for safety)
            policy_result: Dict[str, Any] = await policy.process_request(
                request,
                current_data["target_url"],
                current_data["headers"].copy(),  # Pass a copy of current headers
                current_data["body"],
            )

            # Prepare the data for the *next* policy based on the current result
            next_data: RequestData = current_data.copy()  # Start with a copy of current state

            # Merge headers from policy result into next_data
            policy_headers = policy_result.pop("headers", None)
            if isinstance(policy_headers, dict):
                # Create a new merged dictionary for headers
                next_data["headers"] = {**current_data["headers"], **policy_headers}
            elif policy_headers is not None:
                logging.warning(f"Policy {policy.__class__.__name__} returned non-dict headers: {policy_headers}")
                # Keep previous headers if policy result was invalid
                next_data["headers"] = current_data["headers"].copy()
            else:
                # No headers returned by policy, keep existing ones
                next_data["headers"] = current_data["headers"].copy()

            # Update remaining fields in next_data from policy_result
            for key, value in policy_result.items():
                if key in RequestData.__required_keys__ or key in RequestData.__optional_keys__:
                    # Type checking might be needed here for robustness
                    next_data[key] = value  # type: ignore
                else:
                    # Policy returned an unexpected key, ignore it for now
                    pass

            # Update current_data for the next iteration
            current_data = next_data

        return current_data  # Return the final state after all policies

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
