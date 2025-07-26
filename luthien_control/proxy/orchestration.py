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
from luthien_control.proxy.debugging import create_debug_response, log_policy_execution, log_transaction_state
from luthien_control.settings import Settings

logger = logging.getLogger(__name__)


def _initialize_transaction(body: bytes, url: str, api_key: str) -> Transaction:
    transaction_id = uuid.uuid4()
    openai_api_request = fastapi_request_to_openai_chat_completions_request(body)
    request = Request(payload=openai_api_request, api_endpoint=url, api_key=api_key)
    return Transaction(transaction_id=transaction_id, openai_request=request, openai_response=Response())


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
        },
    )

    # 2. Apply the main policy
    policy_start_time = None
    try:
        logger.info(
            "Applying control policy",
            extra={
                "transaction_id": str(transaction.transaction_id),
                "policy_name": main_policy.name,
                "url": url,
                "method": request.method,
            },
        )
        policy_start_time = time.time()
        transaction = await main_policy.apply(transaction=transaction, container=dependencies, session=session)

        # Log successful policy execution
        log_policy_execution(
            str(transaction.transaction_id),
            main_policy.name or "unknown",
            "completed",
            duration=time.time() - policy_start_time if policy_start_time else None,
            details={"has_response": transaction.openai_response.payload is not None},
        )

        logger.info(
            "Policy execution complete",
            extra={
                "transaction_id": str(transaction.transaction_id),
                "policy_name": main_policy.name,
                "duration_seconds": time.time() - policy_start_time if policy_start_time else None,
            },
        )
        if transaction.openai_response.payload is not None:
            final_response = openai_chat_completions_response_to_fastapi_response(transaction.openai_response.payload)
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
            },
        )

        logger.warning(
            f"Control policy error - transaction {transaction.transaction_id}",
            extra={
                "transaction_id": str(transaction.transaction_id),
                "error": str(e),
                "error_type": e.__class__.__name__,
                "policy_name": getattr(e, "policy_name", "unknown"),
            },
        )
        # Directly build a JSONResponse for policy errors
        policy_name_for_error = getattr(e, "policy_name", "unknown")
        status_code = getattr(e, "status_code", None) or status.HTTP_400_BAD_REQUEST  # Use 400 if None or not specified
        error_detail = getattr(e, "detail", str(e))  # Use str(e) if no detail attribute

        # Check if we're in dev mode and if the exception has debug info
        settings = Settings()
        debug_details = None

        if settings.dev_mode():
            # Check if the ControlPolicyError itself has debug info
            if hasattr(e, "debug_info"):
                debug_details = e.debug_info  # type: ignore
            # Check if the underlying exception (__cause__) has debug info
            elif hasattr(e, "__cause__") and hasattr(e.__cause__, "debug_info"):
                debug_details = e.__cause__.debug_info  # type: ignore

        # Use create_debug_response to generate the response
        response_content = create_debug_response(
            status_code=status_code,
            message=f"Policy error in '{policy_name_for_error}': {error_detail}",
            transaction_id=str(transaction.transaction_id),
            details=debug_details,
            include_debug_info=settings.dev_mode(),
        )

        final_response = JSONResponse(
            status_code=status_code,
            content=response_content,
        )

    except Exception as e:
        # Log unexpected error
        policy_duration = time.time() - policy_start_time if policy_start_time else None
        log_policy_execution(
            str(transaction.transaction_id),
            main_policy.name or "unknown",
            "error",
            duration=policy_duration,
            error=str(e),
            details={
                "error_type": e.__class__.__name__,
                "unexpected": True,
            },
        )

        # Handle unexpected errors during initialization or policy execution
        logger.exception(
            f"Unhandled exception during policy flow - transaction {transaction.transaction_id}",
            extra={
                "transaction_id": str(transaction.transaction_id),
                "error": str(e),
                "error_type": e.__class__.__name__,
            },
        )
        # Try to build an error response using the builder
        policy_name_for_error = getattr(main_policy, "name", main_policy.__class__.__name__)

        # Check if we're in dev mode and if the exception has debug info
        settings = Settings()
        debug_details = None

        if settings.dev_mode() and hasattr(e, "debug_info"):
            debug_details = e.debug_info  # type: ignore

        # Use create_debug_response to generate the response
        response_content = create_debug_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal Server Error",
            transaction_id=str(transaction.transaction_id),
            details=debug_details,
            include_debug_info=settings.dev_mode(),
        )

        # Add policy name to the response
        response_content["policy_name"] = policy_name_for_error

        final_response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_content,
        )

    return final_response
