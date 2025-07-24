"""Enhanced debugging utilities for the proxy pipeline."""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class DebugLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to add detailed request/response logging for debugging."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        request_id = request.headers.get("x-request-id", "no-id")

        # Log request details
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                request_body = await request.body()

                # Reconstruct request for downstream processing
                async def receive():
                    return {"type": "http.request", "body": request_body}

                request._receive = receive

                # Try to parse JSON for logging
                try:
                    parsed_body = json.loads(request_body) if request_body else None
                    logger.debug(
                        f"[{request_id}] Incoming {request.method} request",
                        extra={
                            "path": request.url.path,
                            "headers": dict(request.headers),
                            "body": parsed_body,
                            "query_params": dict(request.query_params),
                        },
                    )
                except json.JSONDecodeError:
                    logger.debug(
                        f"[{request_id}] Incoming {request.method} request (non-JSON body)",
                        extra={
                            "path": request.url.path,
                            "headers": dict(request.headers),
                            "body_length": len(request_body) if request_body else 0,
                            "query_params": dict(request.query_params),
                        },
                    )
            except Exception as e:
                logger.error(f"[{request_id}] Error reading request body: {e}")
        else:
            logger.debug(
                f"[{request_id}] Incoming {request.method} request",
                extra={
                    "path": request.url.path,
                    "headers": dict(request.headers),
                    "query_params": dict(request.query_params),
                },
            )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response details
        logger.info(
            f"[{request_id}] Request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": duration,
            },
        )

        # Add debug headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time"] = f"{duration:.3f}s"

        return response


def log_transaction_state(transaction_id: str, stage: str, details: Dict[str, Any]) -> None:
    """Log transaction state at various stages of processing."""
    logger.debug(
        f"[{transaction_id}] Transaction state at {stage}",
        extra={"stage": stage, "timestamp": datetime.now(UTC).isoformat(), **details},
    )


def log_policy_execution(
    transaction_id: str,
    policy_name: str,
    status: str,
    duration: Optional[float] = None,
    error: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Log policy execution details."""
    log_data = {
        "transaction_id": transaction_id,
        "policy_name": policy_name,
        "status": status,
    }

    if duration is not None:
        log_data["duration_seconds"] = str(duration)

    if error:
        log_data["error"] = error

    if details:
        log_data.update(details)

    if status == "error":
        logger.error(f"[{transaction_id}] Policy {policy_name} failed", extra=log_data)
    else:
        logger.info(f"[{transaction_id}] Policy {policy_name} {status}", extra=log_data)


def create_debug_response(
    status_code: int,
    message: str,
    transaction_id: str,
    details: Optional[Dict[str, Any]] = None,
    include_debug_info: bool = True,
) -> Dict[str, Any]:
    """Create a detailed error response for debugging."""
    response = {
        "detail": message,
        "transaction_id": transaction_id,
    }

    if include_debug_info and details:
        response["debug"] = str({"timestamp": datetime.now(UTC).isoformat(), **details})

    return response
