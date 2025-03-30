"""Utility functions for the proxy server."""

import zlib
import brotli
from typing import Optional

from fastapi import Request
import httpx


def decompress_content(content: bytes, encoding: Optional[str]) -> bytes:
    """Decompresses content based on the provided encoding.

    Args:
        content: The byte content to decompress.
        encoding: The content encoding (e.g., 'gzip', 'deflate', 'br'). Case-insensitive.

    Returns:
        The decompressed content as bytes.

    Raises:
        ValueError: If the encoding is unsupported or decompression fails.
    """
    # Normalize encoding string
    normalized_encoding = encoding.lower() if encoding else None

    if not normalized_encoding or normalized_encoding == "identity":
        return content
    elif normalized_encoding == "gzip":
        # The wbits parameter +32 is undocumented, but needed for zlib to auto-detect header/checksum
        # 16 + MAX_WBITS is also common for gzip
        try:
            return zlib.decompress(content, wbits=16 + zlib.MAX_WBITS)
        except zlib.error as e:
            raise ValueError(f"Failed to decompress gzip content: {e}") from e
    elif normalized_encoding == "deflate":
        # Negative wbits indicates raw deflate stream without zlib header/checksum
        try:
            return zlib.decompress(content, wbits=-zlib.MAX_WBITS)
        except zlib.error as e:
            # Some servers might send deflate with zlib header, try that as fallback
            try:
                return zlib.decompress(content, wbits=zlib.MAX_WBITS)
            except zlib.error:
                raise ValueError(f"Failed to decompress deflate content: {e}") from e # Raise original error
    elif normalized_encoding == "br":
        try:
            return brotli.decompress(content)
        except brotli.error as e:
            raise ValueError(f"Failed to decompress brotli content: {e}") from e
    else:
        raise ValueError(f"Unsupported encoding: {encoding}")


async def get_decompressed_request_body(request: Request) -> bytes:
    """Gets the request body, decompressing it if necessary based on Content-Encoding.

    Args:
        request: The FastAPI Request object.

    Returns:
        The (potentially decompressed) request body as bytes.
    """
    raw_body = await request.body()
    encoding = request.headers.get("content-encoding")
    # Pass raw_body and encoding to the decompression logic
    return decompress_content(raw_body, encoding)


async def get_decompressed_response_body(response: httpx.Response) -> bytes:
    """Reads and decompresses the response body if necessary based on Content-Encoding.

    NOTE: This consumes the response stream.

    Args:
        response: An httpx.Response object.

    Returns:
        The (potentially decompressed) response body as bytes.
    """
    raw_body = await response.aread() # Reads the entire body
    encoding = response.headers.get("content-encoding")
     # Pass raw_body and encoding to the decompression logic
    return decompress_content(raw_body, encoding) 