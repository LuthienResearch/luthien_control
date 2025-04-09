import uuid
from typing import Sequence
import logging

import fastapi
import httpx

from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext
from luthien_control.core.response_builder.interface import ResponseBuilder

# Get a logger for this module
logger = logging.getLogger(__name__)


async def run_policy_flow(
    request: fastapi.Request,
    policies: Sequence[ControlPolicy],
    builder: ResponseBuilder,
    settings: Settings,
    http_client: httpx.AsyncClient,
    initial_context_policy: InitializeContextPolicy,
) -> fastapi.Response:
    """
    Orchestrates the execution of a sequence of ControlPolicies.

    Args:
        request: The incoming FastAPI request.
        policies: The sequence of policies to execute after initialization.
        builder: The response builder to generate the final response.
        settings: The application settings.
        http_client: The HTTP client for making backend requests.
        initial_context_policy: The policy used to initialize the context.

    Returns:
        The final FastAPI response generated by the builder.
    """
    transaction_id = uuid.uuid4()
    context = TransactionContext(transaction_id=transaction_id)
    # Add http_client and settings to context early for policies to use
    context.settings = settings
    context.http_client = http_client

    try:
        # 1. Apply Initial Policy
        context = await initial_context_policy.apply(context, fastapi_request=request)

        # 2. Apply Main Policies Sequentially
        for policy in policies:
            try:
                context = await policy.apply(context)
            except Exception as policy_exc:
                # Log policy execution error
                logger.error(
                    f"[TXID: {transaction_id}] Policy {type(policy).__name__} failed: {policy_exc}",
                    exc_info=True,  # Include stack trace
                )
                # Stop processing further policies on error
                break

    except Exception as initial_exc:
        # Log initial policy execution error
        logger.error(
            f"[TXID: {transaction_id}] Initial policy {type(initial_context_policy).__name__} failed: {initial_exc}",
            exc_info=True,
        )
        # Context remains as it was before the initial policy failed

    # 3. Build Final Response
    # The builder receives the context in whatever state it was left
    # (either after all policies, or after an error occurred).
    final_response = builder.build_response(context)

    return final_response
