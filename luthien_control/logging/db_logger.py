import logging
from typing import Any, Dict, Optional

from fastapi import Request, Response

# Assuming absolute imports are preferred as per change_guidelines.mdc
from luthien_control.db.database import get_db_pool, log_request_response

logger = logging.getLogger(__name__)


async def log_db_entry(
    request: Request,
    response: Response,
    request_body: Optional[bytes] = None,  # Request body might be consumed already
    response_body: Optional[bytes] = None,  # Response body might be streamed
) -> None:
    """
    Asynchronously logs a request and response pair to the database.

    This function orchestrates fetching the DB pool and calling the
    database insertion function.

    Args:
        request: The FastAPI Request object.
        response: The FastAPI Response object.
        request_body: The raw request body bytes (if available).
        response_body: The raw response body bytes (if available).
    """
    try:
        pool = get_db_pool()

        # TODO: Extract relevant data from request/response objects
        # This needs careful consideration based on what we want to log.
        # Example placeholders:
        request_data: Dict[str, Any] = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": request_body.decode("utf-8", errors="replace") if request_body else None,
            # Add more fields as needed
        }
        response_data: Dict[str, Any] = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_body.decode("utf-8", errors="replace") if response_body else None,
            # Add more fields as needed (e.g., processing time)
        }
        client_ip = request.client.host if request.client else None

        await log_request_response(
            pool=pool,
            request_data=request_data,
            response_data=response_data,
            client_ip=client_ip,
        )
        logger.debug(f"Successfully submitted log entry for request to {request.url}")

    except NotImplementedError:
        # Expected during skeleton phase
        logger.warning(f"Database logging for {request.url} skipped: Not implemented yet.")
    except RuntimeError as e:
        # Catch specific case where DB pool is not initialized
        logger.error(f"Database logging failed: {e}")
    except Exception as e:
        # Catch-all for other unexpected errors during logging
        logger.exception(f"Unexpected error during database logging for {request.url}: {e}")
        # Avoid crashing the main application flow due to logging failures
