#!/usr/bin/env python3
"""
Debug script to capture and compare OpenAI streaming vs non-streaming responses.

This script helps debug the issue where streaming responses can't be converted
to OpenAI response objects by capturing both response types as JSON.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict

import openai


async def capture_non_streaming_response(client: openai.AsyncOpenAI) -> Dict[str, Any]:
    """Capture a non-streaming response from OpenAI chat completions."""
    print("📡 Capturing non-streaming response...")

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Say hello!"}], max_tokens=50, stream=False
    )

    # Convert to dict for JSON serialization
    response_dict = response.model_dump()
    print(f"✅ Non-streaming response captured. Type: {type(response)}")
    print(f"   Has model_dump: {hasattr(response, 'model_dump')}")
    print(f"   Response ID: {response_dict.get('id', 'N/A')}")

    return {
        "response_type": "non_streaming",
        "python_type": str(type(response)),
        "has_model_dump": hasattr(response, "model_dump"),
        "response_data": response_dict,
        "captured_at": datetime.now().isoformat(),
    }


async def capture_streaming_response(client: openai.AsyncOpenAI) -> Dict[str, Any]:
    """Capture a streaming response from OpenAI chat completions."""
    print("🌊 Capturing streaming response...")

    stream = await client.chat.completions.create(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Say hello!"}], max_tokens=50, stream=True
    )

    print(f"✅ Streaming response created. Type: {type(stream)}")
    print(f"   Has model_dump: {hasattr(stream, 'model_dump')}")
    print(f"   Has __aiter__: {hasattr(stream, '__aiter__')}")

    # Collect streaming chunks
    chunks = []
    async for chunk in stream:
        chunk_dict = chunk.model_dump() if hasattr(chunk, "model_dump") else str(chunk)
        chunks.append(
            {"chunk_type": str(type(chunk)), "has_model_dump": hasattr(chunk, "model_dump"), "data": chunk_dict}
        )
        if len(chunks) >= 5:  # Limit to first 5 chunks to keep file size reasonable
            break

    print(f"   Collected {len(chunks)} streaming chunks")

    return {
        "response_type": "streaming",
        "python_type": str(type(stream)),
        "has_model_dump": hasattr(stream, "model_dump"),
        "has_aiter": hasattr(stream, "__aiter__"),
        "stream_chunks": chunks,
        "captured_at": datetime.now().isoformat(),
    }


async def main():
    """Main function to capture both response types and save as JSON."""
    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set!")
        print("   If you have a .env file, run this script with:")
        print("   source .env && poetry run python scripts/debug_openai_responses.py")
        print("   Or set it directly:")
        print("   export OPENAI_API_KEY='your-key-here'")
        return

    # Create OpenAI client
    client = openai.AsyncOpenAI(api_key=api_key)

    print("🔍 OpenAI Response Debugging Script")
    print("===================================")
    print(f"OpenAI library version: {openai.__version__}")
    print()

    try:
        # Capture both response types
        non_streaming_data = await capture_non_streaming_response(client)
        streaming_data = await capture_streaming_response(client)

        # Combine data
        debug_data = {
            "script_info": {
                "description": "Debug data for OpenAI streaming vs non-streaming responses",
                "openai_version": openai.__version__,
                "captured_at": datetime.now().isoformat(),
            },
            "non_streaming": non_streaming_data,
            "streaming": streaming_data,
        }

        # Save to JSON file
        output_file = f"openai_response_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

        print()
        print(f"💾 Debug data saved to: {output_file}")
        print()
        print("📊 Summary:")
        print(f"   Non-streaming type: {non_streaming_data['python_type']}")
        print(f"   Non-streaming has model_dump: {non_streaming_data['has_model_dump']}")
        print(f"   Streaming type: {streaming_data['python_type']}")
        print(f"   Streaming has model_dump: {streaming_data['has_model_dump']}")
        print(f"   Streaming has __aiter__: {streaming_data['has_aiter']}")

    except Exception as e:
        print(f"❌ Error during capture: {e}")
        print(f"   Error type: {type(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
