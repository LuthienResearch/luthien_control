"""
Test OpenAI SDK compatibility with our proxy server.
"""
import os
from pathlib import Path
import json
from dotenv import load_dotenv
from openai import OpenAI
import httpx

TARGET_URL = "https://luthien-control.fly.dev"

def test_direct_sdk():
    """Test direct OpenAI SDK usage."""
    print("\n=== Testing Direct SDK Call ===")
    client = OpenAI()  # Uses OPENAI_API_KEY from env by default
    
    try:
        response = client.models.list()
        print("✅ Direct SDK call successful")
        print(f"Models available: {len(response.data)}")
        print("\nFirst few models:")
        for model in response.data[:3]:
            print(f"  - {model.id}")
    except Exception as e:
        print("❌ Direct SDK call failed:")
        print(f"  Error: {str(e)}")
        return None
    
    return response

def test_proxied_sdk():
    """Test SDK usage through our proxy."""
    print("\n=== Testing Proxied SDK ===")
    
    # proxy_url = f"http://{os.getenv('LUTHIEN_HOST', 'localhost')}:{os.getenv('LUTHIEN_PORT', '8000')}/v1"
    # proxy_url = "https://luthien.dev:8000/v1"
    proxy_url = TARGET_URL + "/v1"
    print(f"Configuring SDK with base_url: {proxy_url}")
    
    # Create a custom transport that allows HTTP
    transport = httpx.HTTPTransport(
        verify=False,  # Disable SSL verification
        retries=1
    )
    
    # Create custom HTTP client with the transport
    http_client = httpx.Client(
        transport=transport,
        verify=False,
        follow_redirects=True
    )
    
    # Configure OpenAI client with our custom HTTP client
    client = OpenAI(
        base_url=proxy_url,
        api_key=os.getenv("OPENAI_API_KEY"),
        http_client=http_client
    )
    
    try:
        print("Making request to models endpoint...")
        response = client.models.list()
        print("✅ Proxied SDK call successful")
        print(f"Models available: {len(response.data)}")
        return response
    except Exception as e:
        print("❌ Other error:")
        print(f"  Error type: {type(e)}")
        print(f"  Error message: {str(e)}")
        if hasattr(e, '__cause__'):
            print(f"  Underlying error: {str(e.__cause__)}")
        return None

def compare_responses(direct_response, proxy_response):
    """Compare responses from direct and proxied SDK calls."""
    print("\n=== Comparing Responses ===")
    
    if not (direct_response and proxy_response):
        print("❌ Cannot compare - one or both calls failed")
        return
    
    direct_models = {model.id for model in direct_response.data}
    proxy_models = {model.id for model in proxy_response.data}
    
    if direct_models == proxy_models:
        print("✅ Model lists match exactly")
    else:
        print("❌ Model lists differ:")
        print(f"Models only in direct response: {direct_models - proxy_models}")
        print(f"Models only in proxy response: {proxy_models - direct_models}")

def main():
    """Run SDK compatibility tests."""
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return
    
    # Test health endpoint first
    # proxy_url = f"http://{os.getenv('LUTHIEN_HOST', 'localhost')}:{os.getenv('LUTHIEN_PORT', '8000')}"
    # proxy_url = "https://luthien.dev:8000"
    proxy_url = TARGET_URL
    try:
        health_response = httpx.get(f"{proxy_url}/health", verify=False)
        if health_response.status_code != 200:
            print("❌ Proxy server health check failed")
            return
    except Exception as e:
        print(f"❌ Proxy server may not be running: {e}")
        return
    
    # Run tests
    direct_response = test_direct_sdk()
    proxy_response = test_proxied_sdk()
    
    # Compare results
    compare_responses(direct_response, proxy_response)

if __name__ == "__main__":
    main() 