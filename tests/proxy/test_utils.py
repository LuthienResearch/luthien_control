"""Tests for proxy utility functions."""

import zlib
from unittest.mock import AsyncMock

import brotli
import pytest

# Use absolute import based on change_guidelines.mdc
from luthien_control.proxy.utils import (
    decompress_content,
    get_decompressed_request_body,
    get_decompressed_response_body,
)

# Test data
ORIGINAL_CONTENT = b"This is the original test content."

GZIP_CONTENT = zlib.compress(ORIGINAL_CONTENT, wbits=16 + zlib.MAX_WBITS)  # gzip format
DEFLATE_CONTENT = zlib.compress(ORIGINAL_CONTENT, wbits=-zlib.MAX_WBITS)  # raw deflate
BR_CONTENT = brotli.compress(ORIGINAL_CONTENT)

# === Tests for decompress_content ===


def test_decompress_content_no_encoding():
    assert decompress_content(ORIGINAL_CONTENT, None) == ORIGINAL_CONTENT
    assert decompress_content(ORIGINAL_CONTENT, "") == ORIGINAL_CONTENT
    assert decompress_content(ORIGINAL_CONTENT, "identity") == ORIGINAL_CONTENT


def test_decompress_content_gzip():
    assert decompress_content(GZIP_CONTENT, "gzip") == ORIGINAL_CONTENT
    assert decompress_content(GZIP_CONTENT, "GZIP") == ORIGINAL_CONTENT  # Case-insensitive


def test_decompress_content_deflate():
    assert decompress_content(DEFLATE_CONTENT, "deflate") == ORIGINAL_CONTENT
    assert decompress_content(DEFLATE_CONTENT, "DEFLATE") == ORIGINAL_CONTENT  # Case-insensitive


def test_decompress_content_brotli():
    assert decompress_content(BR_CONTENT, "br") == ORIGINAL_CONTENT
    assert decompress_content(BR_CONTENT, "BR") == ORIGINAL_CONTENT  # Case-insensitive


def test_decompress_content_unsupported():
    with pytest.raises(ValueError, match="Unsupported encoding: unknown"):
        decompress_content(ORIGINAL_CONTENT, "unknown")


# === Tests for get_decompressed_request_body ===


@pytest.mark.asyncio
async def test_get_request_body_no_encoding():
    mock_request = AsyncMock()
    mock_request.headers = {}
    mock_request.body = AsyncMock(return_value=ORIGINAL_CONTENT)
    body = await get_decompressed_request_body(mock_request)
    assert body == ORIGINAL_CONTENT
    mock_request.body.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_request_body_gzip():
    mock_request = AsyncMock()
    mock_request.headers = {"content-encoding": "gzip"}
    mock_request.body = AsyncMock(return_value=GZIP_CONTENT)
    body = await get_decompressed_request_body(mock_request)
    assert body == ORIGINAL_CONTENT
    mock_request.body.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_request_body_deflate():
    mock_request = AsyncMock()
    mock_request.headers = {"content-encoding": "deflate"}
    mock_request.body = AsyncMock(return_value=DEFLATE_CONTENT)
    body = await get_decompressed_request_body(mock_request)
    assert body == ORIGINAL_CONTENT
    mock_request.body.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_request_body_brotli():
    mock_request = AsyncMock()
    mock_request.headers = {"content-encoding": "br"}
    mock_request.body = AsyncMock(return_value=BR_CONTENT)
    body = await get_decompressed_request_body(mock_request)
    assert body == ORIGINAL_CONTENT
    mock_request.body.assert_awaited_once()


# === Tests for get_decompressed_response_body ===


@pytest.mark.asyncio
async def test_get_response_body_no_encoding():
    mock_response = AsyncMock()
    mock_response.headers = {}
    mock_response.aread = AsyncMock(return_value=ORIGINAL_CONTENT)
    body = await get_decompressed_response_body(mock_response)
    assert body == ORIGINAL_CONTENT
    mock_response.aread.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_response_body_gzip():
    mock_response = AsyncMock()
    mock_response.headers = {"content-encoding": "gzip"}
    mock_response.aread = AsyncMock(return_value=GZIP_CONTENT)
    body = await get_decompressed_response_body(mock_response)
    assert body == ORIGINAL_CONTENT
    mock_response.aread.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_response_body_deflate():
    mock_response = AsyncMock()
    mock_response.headers = {"content-encoding": "deflate"}
    mock_response.aread = AsyncMock(return_value=DEFLATE_CONTENT)
    body = await get_decompressed_response_body(mock_response)
    assert body == ORIGINAL_CONTENT
    mock_response.aread.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_response_body_brotli():
    mock_response = AsyncMock()
    mock_response.headers = {"content-encoding": "br"}
    mock_response.aread = AsyncMock(return_value=BR_CONTENT)
    body = await get_decompressed_response_body(mock_response)
    assert body == ORIGINAL_CONTENT
    mock_response.aread.assert_awaited_once()
