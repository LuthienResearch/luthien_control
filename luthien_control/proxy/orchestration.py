import logging
import time
import uuid

import fastapi
from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.api.openai_chat_completions.request import (
    fastapi_request_to_openai_chat_completions_request,
)
from luthien_control.api.openai_chat_completions.response import openai_chat_completions_response_to_fastapi_response
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.proxy.debugging import log_policy_execution, log_transaction_state

logger = logging.getLogger(__name__)


def _initialize_transaction(body: bytes, url: str, api_key: str) -> Transaction:
    transaction_id = uuid.uuid4()
    openai_api_request = fastapi_request_to_openai_chat_completions_request(body)
    request = Request(payload=openai_api_request, api_endpoint=url, api_key=api_key)
    return Transaction(transaction_id=transaction_id, request=request, response=Response())


async def run_policy_flow(
    request: fastapi.Request,
    main_policy: ControlPolicy,
    dependencies: DependencyContainer,
    session: AsyncSession,
) -> fastapi.Response:
    """
    Orchestrates the execution of the main ControlPolicy using injected dependencies.
    Exceptions raised by policies are expected to be caught by FastAPI exception handlers.

    Args:
        request: The incoming FastAPI request.
        main_policy: The main policy instance to execute.
        dependencies: The application's dependency container.
        session: The database session for this request.

    Returns:
        The final FastAPI response.
    """
    # 1. Initialize Context
    body = await request.body()
    url = request.path_params["full_path"]
    api_key = request.headers.get("authorization", "").replace("Bearer ", "")
    transaction = _initialize_transaction(body, url, api_key)

    # Log initial transaction state
    log_transaction_state(
        str(transaction.transaction_id),
        "initialization",
        {
            "url": url,
            "method": request.method,
            "has_api_key": bool(api_key),
            "body_length": len(body) if body else 0,
            "headers_count": len(request.headers),
        }
    )

    # 2. Apply the main policy
    policy_start_time = None
    try:
        logger.info(f"[{transaction.transaction_id}] Applying main policy: {main_policy.name}")
        policy_start_time = time.time()
        transaction = await main_policy.apply(transaction=transaction, container=dependencies, session=session)

        # Log successful policy execution
        log_policy_execution(
            str(transaction.transaction_id),
            main_policy.name or "unknown",
            "completed",
            duration=time.time() - policy_start_time if policy_start_time else None,
            details={"has_response": transaction.response.payload is not None}
        )

        logger.info(f"[{transaction.transaction_id}] Policy execution complete. Building final response.")
        if transaction.response.payload is not None:
            final_response = openai_chat_completions_response_to_fastapi_response(transaction.response.payload)
        else:
            final_response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal Server Error: No response payload",
                    "transaction_id": str(transaction.transaction_id),
                    "policy_name": main_policy.name,
                },
            )

    except ControlPolicyError as e:
        # Log policy error
        policy_duration = time.time() - policy_start_time if policy_start_time else None
        log_policy_execution(
            str(transaction.transaction_id),
            main_policy.name or "unknown",
            "error",
            duration=policy_duration,
            error=str(e),
            details={
                "error_type": e.__class__.__name__,
                "policy_name": getattr(e, "policy_name", "unknown"),
            }
        )

        logger.warning(f"[{transaction.transaction_id}] Control policy error halted execution: {e}")
        # Directly build a JSONResponse for policy errors
        policy_name_for_error = getattr(e, "policy_name", "unknown")
        status_code = getattr(e, "status_code", None) or status.HTTP_400_BAD_REQUEST  # Use 400 if None or not specified
        error_detail = getattr(e, "detail", str(e))  # Use str(e) if no detail attribute

        final_response = JSONResponse(
            status_code=status_code,
            content={
                "detail": f"Policy error in '{policy_name_for_error}': {error_detail}",
                "transaction_id": str(transaction.transaction_id),
            },
        )

    except Exception as e:
        # Log unexpected error
        policy_duration = time.time() - policy_start_time if policy_start_time else None
        log_policy_execution(
            str(transaction.transaction_id),
            main_policy.name,
            "error",
            duration=policy_duration,
            error=str(e),
            details={
                "error_type": e.__class__.__name__,
                "unexpected": True,
            }
        )

        # Handle unexpected errors during initialization or policy execution
        logger.exception(f"[{transaction.transaction_id}] Unhandled exception during policy flow: {e}")
        # Try to build an error response using the builder
        policy_name_for_error = getattr(main_policy, "name", main_policy.__class__.__name__)
        final_response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal Server Error",
                "transaction_id": str(transaction.transaction_id),
                "policy_name": policy_name_for_error,
            },
        )

    return final_response
