"""Simple implementations of the ResponseBuilder interface."""

from fastapi import Response, status
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.core.transaction_context import TransactionContext


class SimpleResponseBuilder(ResponseBuilder):
    """A basic response builder that attempts to use context.response."""

    def build_response(self, context: TransactionContext) -> Response:
        """Builds a response, preferring context.response if available, otherwise returns a 500 error."""
        if context.response is None:
            self.logger.error(f"No response generated for transaction {context.transaction_id}.")
            return Response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=(
                    f'{{"detail": "Internal server error: No response generated for transaction '
                    f'{context.transaction_id}"}}'
                ),
                media_type="application/json",
            )

        # Ensure content is bytes for FastAPI Response
        content: bytes | None
        if isinstance(context.response.content, str):
            content = context.response.content.encode(context.response.encoding or "utf-8")
        elif isinstance(context.response.content, bytes):
            content = context.response.content
        else:
            # Handle cases where content might be None or other types if necessary
            self.logger.warning(
                f"[{context.transaction_id}] Response content is not a string or bytes: {context.response.content}"
            )
            content = b""

        return Response(
            status_code=context.response.status_code,
            content=content,
            headers=dict(context.response.headers),
            # media_type can often be inferred from headers, but explicitly setting might be safer
            media_type=context.response.headers.get("content-type"),
        )
