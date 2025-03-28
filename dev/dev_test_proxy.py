"""
Test script for the Luthien Control proxy server.
"""
import os
import json
from pathlib import Path
import httpx
from dotenv import load_dotenv

async def main():
    """Test the proxy server by making requests to various endpoints."""
    # Load environment variables
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
    
    # Get proxy URL from environment or use default
    proxy_url = f"http://{os.getenv('LUTHIEN_HOST', 'localhost')}:{os.getenv('LUTHIEN_PORT', '8000')}"
    
    # Test models endpoint
    print(f"\nTesting GET {proxy_url}/v1/models")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{proxy_url}/v1/models",
            headers={"Accept-Encoding": "identity"}
        )
        print(f"Status: {response.status_code}")
        print("Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print("\nResponse Content:")
        print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 