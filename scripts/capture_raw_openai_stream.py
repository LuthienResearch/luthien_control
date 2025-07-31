#!/usr/bin/env python3
"""
Script to capture raw OpenAI streaming response over HTTP to see the exact SSE format.

This bypasses the OpenAI Python client to see the raw bytes sent by OpenAI's API.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


async def capture_raw_openai_stream() -> Dict[str, Any]:
    """Capture raw OpenAI streaming response directly via HTTP."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    print("🌊 Capturing raw OpenAI streaming response via HTTP...")

    # Prepare the request payload
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Say hello in exactly 5 words!"}],
        "max_tokens": 20,
        "stream": True,
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Make raw HTTP request to OpenAI
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", "https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=30.0
        ) as response:
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")

            raw_chunks = []
            raw_bytes = b""

            async for chunk in response.aiter_bytes():
                raw_bytes += chunk
                # Decode and store each chunk
                try:
                    chunk_text = chunk.decode("utf-8")
                    raw_chunks.append({"raw_bytes": chunk.hex(), "decoded_text": chunk_text, "length": len(chunk)})
                except UnicodeDecodeError:
                    raw_chunks.append({"raw_bytes": chunk.hex(), "decoded_text": "[BINARY DATA]", "length": len(chunk)})

                # Stop after reasonable amount of data
                if len(raw_chunks) >= 20:
                    break

    # Try to parse the complete raw response as text
    complete_text = ""
    try:
        complete_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        complete_text = "[CONTAINS BINARY DATA]"

    return {
        "capture_method": "raw_http",
        "response_status": response.status_code,
        "response_headers": dict(response.headers),
        "raw_chunks": raw_chunks,
        "complete_raw_text": complete_text,
        "total_bytes": len(raw_bytes),
        "captured_at": datetime.now().isoformat(),
    }


async def main():
    """Main function to capture raw streaming data."""

    print("🔍 Raw OpenAI Streaming Capture")
    print("===============================")

    try:
        raw_data = await capture_raw_openai_stream()

        # Save to JSON file
        output_file = f"raw_openai_stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Raw stream data saved to: {output_file}")
        print(f"📊 Total bytes captured: {raw_data['total_bytes']}")
        print(f"📦 Number of chunks: {len(raw_data['raw_chunks'])}")
        print(f"🔍 Response headers: {raw_data['response_headers']}")

        # Show first few lines of the response
        lines = raw_data["complete_raw_text"].split("\n")[:10]
        print("\n📝 First 10 lines of response:")
        for i, line in enumerate(lines, 1):
            print(f"   {i:2d}: {repr(line)}")

    except Exception as e:
        print(f"❌ Error during capture: {e}")
        print(f"   Error type: {type(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
