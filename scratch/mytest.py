import os
import json
import io
import brotli
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Create a custom transport that does NO automatic decompression
class NoDecompressionTransport(httpx.BaseTransport):
    def __init__(self):
        self._transport = httpx.HTTPTransport()
    
    def handle_request(self, request):
        # Always force Accept-Encoding to identity (no compression)
        request.headers["Accept-Encoding"] = "identity"
        return self._transport.handle_request(request)

def process_response(response, label=""):
    """Process a response, handling any compression."""
    print(f"\n--- {label} Response ---")
    print(f"Status: {response.status_code}")
    print("Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    
    # Get raw bytes to avoid any automatic processing
    raw_content = response.read()
    print(f"Raw content length: {len(raw_content)} bytes")
    
    # Check for encoding header
    content_encoding = response.headers.get('content-encoding', '').lower()
    print(f"Content-Encoding: {content_encoding}")
    
    content = raw_content
    # Handle brotli encoding if present
    if content_encoding and 'br' in content_encoding:
        print("Detected brotli encoding, attempting to decompress...")
        try:
            # Use explicit brotli decompression
            content = brotli.decompress(raw_content)
            print(f"Successfully decompressed brotli content, new length: {len(content)} bytes")
        except Exception as e:
            print(f"Error decompressing brotli: {e}")
            print(f"First 20 bytes (hex): {raw_content[:20].hex()}")
            # Save the raw content for debugging
            with open(f"raw_response_{label.lower().replace(' ', '_')}.bin", "wb") as f:
                f.write(raw_content)
            print(f"Saved raw content to raw_response_{label.lower().replace(' ', '_')}.bin for debugging")
            return None
    
    # Try to parse as JSON
    try:
        if content:
            # Try to decode as UTF-8 first
            text = content.decode('utf-8')
            data = json.loads(text)
            print("\nResponse Content (preview):")
            # Print just a subset of data for brevity
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 5:
                preview = {
                    "data": data["data"][:3] + ["..."] + [data["data"][-1]],
                    "object": data.get("object", ""),
                }
                print(json.dumps(preview, indent=2))
            else:
                print(json.dumps(data, indent=2))
            return data
        else:
            print("\nNo content in response")
            return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Error processing content: {e}")
        print(f"Content preview (first 100 bytes): {content[:100]}")
        return None

def main():
    """Test the proxy server by making requests to various endpoints and comparing with direct API calls."""
    # Load environment variables
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        return
    
    # Get proxy URL from environment or use default
    proxy_url = f"http://{os.getenv('LUTHIEN_HOST', 'localhost')}:{os.getenv('LUTHIEN_PORT', '8000')}"
    openai_url = "https://api.openai.com"
    
    # Test health endpoint first
    print("\n==== Testing Health Endpoint ====")
    with httpx.Client(transport=NoDecompressionTransport()) as client:
        try:
            health_response = client.get(f"{proxy_url}/health")
            print(f"Health Check Status: {health_response.status_code}")
            print(f"Health Check Response: {health_response.text}")
        except httpx.RequestError as e:
            print(f"Health Check Failed: {e}")
            print("❌ Proxy server may not be running!")
            return
    
    # Test models endpoint - first directly to OpenAI API
    print("\n==== Testing GET /v1/models ====")
    print(f"\nDirect API Call: {openai_url}/v1/models")
    
    # Create transport for both clients
    transport = NoDecompressionTransport()
    
    # Test direct API call
    with httpx.Client(transport=transport) as client:
        # Print request details before sending
        print("\n=== Direct Request Details ===")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Python/httpx-test",
        }
        print(f"URL: {openai_url}/v1/models")
        print("Request Headers:")
        for key, value in headers.items():
            print(f"  {key}: {value if key != 'Authorization' else 'Bearer [REDACTED]'}")
        
        # Print the actual request object details
        request = client.build_request("GET", f"{openai_url}/v1/models", headers=headers)
        print("\nFull Request Details:")
        print(f"Method: {request.method}")
        print(f"URL: {request.url}")
        print(f"Headers:")
        for key, value in request.headers.items():
            print(f"  {key}: {value if key != 'authorization' else 'Bearer [REDACTED]'}")
        
        direct_response = client.get(
            f"{openai_url}/v1/models",
            headers=headers,
        )
        
        # Print raw response details
        print("\nDirect Response Details:")
        print(f"Status Code: {direct_response.status_code}")
        print("Response Headers:", json.dumps(dict(direct_response.headers), indent=2))
        print("Raw Response Text:", direct_response.text)
        
        direct_data = process_response(direct_response, "Direct API")
    
    # Test proxy call
    print(f"\nProxy API Call: {proxy_url}/v1/models")
    with httpx.Client(transport=transport) as client:
        try:
            print("\n=== Proxy Request Details ===")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Python/httpx-test",
            }
            print(f"URL: {proxy_url}/v1/models")
            print("Request Headers:")
            for key, value in headers.items():
                print(f"  {key}: {value if key != 'Authorization' else 'Bearer [REDACTED]'}")
            
            # Print the actual request object details
            request = client.build_request("GET", f"{proxy_url}/v1/models", headers=headers)
            print("\nFull Request Details:")
            print(f"Method: {request.method}")
            print(f"URL: {request.url}")
            print(f"Headers:")
            for key, value in request.headers.items():
                print(f"  {key}: {value if key != 'authorization' else 'Bearer [REDACTED]'}")
            
            proxy_response = client.get(
                f"{proxy_url}/v1/models",
                headers=headers,
            )
            
            # Print raw response details
            print("\nResponse Details:")
            print(f"Status Code: {proxy_response.status_code}")
            print("Response Headers:", json.dumps(dict(proxy_response.headers), indent=2))
            print("Raw Response Text:", proxy_response.text)
            
            proxy_data = process_response(proxy_response, "Proxy")
        except httpx.RequestError as e:
            print(f"Request Error: {e}")
        except Exception as e:
            print(f"Unexpected Error: {e}")
    
    # Compare responses
    if direct_data and proxy_data:
        print("\n==== Comparison Summary ====")
        print(f"Direct API models count: {len(direct_data.get('data', []))}")
        print(f"Proxy API models count: {len(proxy_data.get('data', []))}")
        
        # Check if models match
        direct_ids = {model["id"] for model in direct_data.get("data", [])}
        proxy_ids = {model["id"] for model in proxy_data.get("data", [])}
        
        if direct_ids == proxy_ids:
            print("✅ Model IDs match exactly")
        else:
            print("❌ Model IDs differ")
            print(f"Models only in Direct API: {direct_ids - proxy_ids}")
            print(f"Models only in Proxy API: {proxy_ids - direct_ids}")
    else:
        print("\n❌ Unable to compare responses - one or both requests failed")

if __name__ == "__main__":
    main()