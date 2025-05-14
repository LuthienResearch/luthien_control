import logging
import uuid

import fastapi
import httpx
from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.response_builder import ResponseBuilder
from luthien_control.core.transaction_context import TransactionContext

logger = logging.getLogger(__name__)


def _initialize_context(fastapi_request: fastapi.Request, body: bytes) -> TransactionContext:
    transaction_id = uuid.uuid4()
    context = TransactionContext(transaction_id=transaction_id)
    method = fastapi_request.method
    url = fastapi_request.path_params["full_path"]
    headers = fastapi_request.headers.raw
    params = fastapi_request.query_params
    context.request = httpx.Request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        content=body,
    )
    return context


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
    context = _initialize_context(request, body)

    builder = ResponseBuilder()

    # 2. Apply the main policy
    try:
        policy_name = getattr(main_policy, "name", main_policy.__class__.__name__)
        logger.info(f"[{context.transaction_id}] Applying main policy: {policy_name}")

        # Call apply directly with context, container (dependencies), and session
        context = await main_policy.apply(context=context, container=dependencies, session=session)

        # Always call the builder after successful policy execution
        logger.info(f"[{context.transaction_id}] Policy execution complete. Building final response.")
        final_response = builder.build_response(context)

    except ControlPolicyError as e:
        logger.warning(f"[{context.transaction_id}] Control policy error halted execution: {e}")
        # Directly build a JSONResponse for policy errors
        policy_name_for_error = getattr(e, "policy_name", "unknown")
        status_code = getattr(e, "status_code", status.HTTP_400_BAD_REQUEST)  # Use 400 if not specified
        error_detail = getattr(e, "detail", str(e))  # Use str(e) if no detail attribute

        final_response = JSONResponse(
            status_code=status_code,
            content={
                "detail": f"Policy error in '{policy_name_for_error}': {error_detail}",
                "transaction_id": str(context.transaction_id),
            },
        )

    except Exception as e:
        # Handle unexpected errors during initialization or policy execution
        logger.exception(f"[{context.transaction_id}] Unhandled exception during policy flow: {e}")
        # Try to build an error response using the builder
        policy_name_for_error = getattr(main_policy, "name", main_policy.__class__.__name__)
        try:
            final_response = builder.build_response(context)
        except Exception as build_e:
            # Log the exception that occurred *during response building*
            logger.exception(
                f"[{context.transaction_id}] Exception occurred *during* error response building: "
                f"{build_e}. Original error was: {e}"
            )
            # Fallback to a basic JSONResponse, mentioning both errors if possible
            error_detail = f"Internal Server Error while processing policy '{policy_name_for_error}'."
            if dependencies.settings.dev_mode():
                # Include more detail if available
                error_detail += f" Initial error: {e}. Error during response building: {build_e}"
                error_detail += f"\n\nFull request: {context.request}"
            final_response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": error_detail,
                    "transaction_id": str(context.transaction_id),
                },
            )

    return final_response
