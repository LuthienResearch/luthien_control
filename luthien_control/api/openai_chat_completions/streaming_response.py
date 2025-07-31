"""Streaming response handling for OpenAI chat completions."""

import logging
from typing import AsyncIterator, Optional

from fastapi.responses import StreamingResponse

from luthien_control.core.streaming_response import StreamingResponseIterator
from luthien_control.utils.streaming import format_openai_streaming_chunk, format_streaming_error

logger = logging.getLogger(__name__)


async def openai_streaming_iterator_to_sse(
    iterator: StreamingResponseIterator, transaction_id: Optional[str] = None
) -> AsyncIterator[str]:
    """Convert an OpenAI streaming iterator to SSE format.

    Args:
        iterator: The streaming iterator from OpenAI
        transaction_id: Optional transaction ID for error reporting

    Yields:
        SSE-formatted strings
    """
    try:
        async for chunk in iterator:
            # Debug log each chunk
            logger.debug(
                "Streaming chunk received",
                extra={
                    "transaction_id": transaction_id,
                    "chunk_type": type(chunk).__name__,
                    "chunk_content": str(chunk)[:200] + "..." if len(str(chunk)) > 200 else str(chunk),
                },
            )

            # Format the chunk as SSE
            formatted_chunk = await format_openai_streaming_chunk(chunk)

            # Debug log the formatted chunk
            logger.debug(
                "Formatted streaming chunk",
                extra={
                    "transaction_id": transaction_id,
                    "formatted_length": len(formatted_chunk),
                    "formatted_preview": formatted_chunk[:100] + "..."
                    if len(formatted_chunk) > 100
                    else formatted_chunk,
                },
            )

            yield formatted_chunk

    except Exception as e:
        logger.error("Error during streaming", exc_info=True)
        # Send generic error in SSE format
        yield await format_streaming_error(e, transaction_id)

    # finally:
    #     # Send final SSE termination
    #     yield "event: done\ndata: [DONE]\n\n"


def openai_streaming_response_to_fastapi_response(
    streaming_iterator: StreamingResponseIterator, transaction_id: Optional[str] = None
) -> StreamingResponse:
    """Convert an OpenAI streaming iterator to a FastAPI StreamingResponse.

    Args:
        streaming_iterator: The streaming iterator containing OpenAI response chunks
        transaction_id: Optional transaction ID for error reporting

    Returns:
        FastAPI StreamingResponse configured for SSE
    """
    # Create SSE iterator
    sse_iterator = openai_streaming_iterator_to_sse(streaming_iterator, transaction_id)

    # Return StreamingResponse with appropriate headers
    return StreamingResponse(
        sse_iterator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )
