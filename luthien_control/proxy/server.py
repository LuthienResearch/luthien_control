"""
FastAPI proxy server implementation for AI model API control.
"""
from typing import Any, Dict, Optional
import os
from pathlib import Path
import brotli

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.datastructures import Headers

from ..logging.api_logger import APILogger
from ..policies.manager import PolicyManager
import litellm
import json
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Set up API logger
api_logger = APILogger(log_file="logs/api.log")

# Create policy manager
policy_manager = PolicyManager()

# Configure LiteLLM
litellm.set_verbose = True  # Enable debugging for testing
# For testing without real API keys, we can use test mode
import os
if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") in ["your_openai_api_key_here", "your_api_key_here"]:
    # Set up test/mock mode
    litellm.secret_manager_client = None  # Disable secret management for testing

# Create FastAPI app
app = FastAPI(title="Luthien Control Framework")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProxyConfig(BaseModel):
    """Configuration for the proxy server."""
    target_url: str
    api_key: Optional[str] = None

# Global configuration - in production, this should be loaded from environment/config
config = ProxyConfig(
    target_url="https://api.openai.com/v1",
    api_key=os.getenv("OPENAI_API_KEY")  # Load API key from environment
)

def get_headers(request: Request) -> Headers:
    """Get headers for the proxy request."""
    # Create a Headers instance from the request headers (excluding any headers with the key "authorization")
    header_dict = {
        k: v for k, v in request.headers.items() if k.lower() != "authorization"
    }
    header_dict["Authorization"] = f"Bearer {config.api_key}"
    header_dict.pop("host", None)
    header_dict.pop("content-length", None)
    headers = Headers(header_dict)
    return headers

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/v1/test/chat/completions")
async def test_litellm_integration(request: Request):
    """
    Test LiteLLM integration without requiring real API keys.
    Returns mock response to validate the integration flow.
    """
    try:
        # Parse request body
        request_body = await request.body()
        request_data = json.loads(request_body)
        
        # Log request details
        api_logger.log_request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            body=request_body,
            query_params=dict(request.query_params)
        )
        
        # Apply request policies
        processed_request = await policy_manager.apply_request_policies(
            request, 
            str(request.url), 
            dict(request.headers), 
            request_body
        )
        
        # Create mock response in OpenAI format
        mock_response = {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1699000000,
            "model": request_data.get('model', 'gpt-3.5-turbo'),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"✅ LiteLLM integration test successful! Processed model: {request_data.get('model', 'gpt-3.5-turbo')}"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }
        
        response_json = json.dumps(mock_response)
        
        # Log response details
        api_logger.log_response(
            status_code=200,
            headers={"content-type": "application/json"},
            body=response_json.encode()
        )
        
        # Apply response policies
        mock_response_obj = type('MockResponse', (), {
            'status_code': 200,
            'headers': {"content-type": "application/json"}
        })()
        
        processed_response = await policy_manager.apply_response_policies(
            request,
            mock_response_obj,
            response_json.encode()
        )
        
        return Response(
            content=processed_response['content'],
            status_code=processed_response['status_code'],
            headers=processed_response['headers'],
            media_type="application/json"
        )
        
    except Exception as e:
        logger.error(f"Error in test integration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test integration error: {str(e)}")

@app.post("/v1/chat/completions")
async def litellm_chat_completions(request: Request):
    """
    Handle chat completion requests using LiteLLM library.
    """
    try:
        # Parse request body
        request_body = await request.body()
        request_data = json.loads(request_body)
        
        # Log request details
        api_logger.log_request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            body=request_body,
            query_params=dict(request.query_params)
        )
        
        # Apply request policies
        processed_request = await policy_manager.apply_request_policies(
            request, 
            str(request.url), 
            dict(request.headers), 
            request_body
        )
        
        # Extract processed data
        processed_body = json.loads(processed_request['body']) if processed_request['body'] else request_data
        
        # Use LiteLLM to handle the completion
        response = await litellm.acompletion(
            model=processed_body.get('model', 'gpt-3.5-turbo'),
            messages=processed_body['messages'],
            temperature=processed_body.get('temperature'),
            max_tokens=processed_body.get('max_tokens'),
            top_p=processed_body.get('top_p'),
            frequency_penalty=processed_body.get('frequency_penalty'),
            presence_penalty=processed_body.get('presence_penalty'),
            stop=processed_body.get('stop'),
            stream=processed_body.get('stream', False)
        )
        
        # Convert response to dict
        response_dict = response.model_dump() if hasattr(response, 'model_dump') else dict(response)
        response_json = json.dumps(response_dict)
        
        # Log response details
        api_logger.log_response(
            status_code=200,
            headers={"content-type": "application/json"},
            body=response_json.encode()
        )
        
        # Apply response policies (create mock response object for compatibility)
        mock_response = type('MockResponse', (), {
            'status_code': 200,
            'headers': {"content-type": "application/json"}
        })()
        
        processed_response = await policy_manager.apply_response_policies(
            request,
            mock_response,
            response_json.encode()
        )
        
        return Response(
            content=processed_response['content'],
            status_code=processed_response['status_code'],
            headers=processed_response['headers'],
            media_type="application/json"
        )
        
    except Exception as e:
        logger.error(f"Error in LiteLLM chat completion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LiteLLM completion error: {str(e)}")

@app.post("/v1/litellm-proxy/chat/completions")
async def litellm_proxy_chat_completions(request: Request):
    """
    Handle chat completion requests using LiteLLM proxy server (Option A).
    """
    from ..integrations.litellm_manager import get_litellm_manager
    
    litellm_manager = get_litellm_manager()
    
    # Ensure LiteLLM proxy is running
    if not litellm_manager.is_running():
        logger.info("Starting LiteLLM proxy server...")
        started = await litellm_manager.start()
        if not started:
            raise HTTPException(status_code=503, detail="Failed to start LiteLLM proxy server")
    
    try:
        # Parse request body
        request_body = await request.body()
        
        # Log request details
        api_logger.log_request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            body=request_body,
            query_params=dict(request.query_params)
        )
        
        # Apply request policies
        processed_request = await policy_manager.apply_request_policies(
            request, 
            str(request.url), 
            dict(request.headers), 
            request_body
        )
        
        # Forward to LiteLLM proxy server
        litellm_url = litellm_manager.get_endpoint_url("v1/chat/completions")
        
        # Prepare headers for LiteLLM proxy
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                litellm_url,
                headers=headers,
                content=processed_request['body'],
                timeout=300  # 5 minute timeout for LLM requests
            )
            
            # Read response content
            content = await response.aread()
            
            # Log response details
            api_logger.log_response(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=content
            )
            
            # Apply response policies
            processed_response = await policy_manager.apply_response_policies(
                request,
                response,
                content
            )
            
            return Response(
                content=processed_response['content'],
                status_code=processed_response['status_code'],
                headers=processed_response['headers']
            )
            
    except Exception as e:
        logger.error(f"Error in LiteLLM proxy completion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LiteLLM proxy error: {str(e)}")

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(request: Request, path: str):
    """
    Forward requests to the target API and log the interaction.
    """
    # Construct target URL
    target_url = f"{config.target_url}/{path}"
    
    # Get headers
    headers = dict(get_headers(request))
    
    # Forward body if present
    body = await request.body() if request.method in ["POST", "PUT"] else None
    
    # Log request details using our API logger
    api_logger.log_request(
        method=request.method,
        url=target_url,
        headers=headers,
        body=body,
        query_params=dict(request.query_params)
    )
    
    try:
        # Apply request policies
        processed_request = await policy_manager.apply_request_policies(
            request, 
            target_url, 
            headers, 
            body
        )
        
        # Use the processed request data
        target_url = processed_request['target_url']
        headers = processed_request['headers']
        body = processed_request['body']
        
        # Forward request
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params
            )
            
            # Read response content once
            content = await response.aread()
            
            # Log response details using our API logger
            api_logger.log_response(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=content
            )

            # Apply response policies
            processed_response = await policy_manager.apply_response_policies(
                request,
                response,
                content
            )
            
            # Use the processed response data
            status_code = processed_response['status_code']
            headers_dict = processed_response['headers']
            content = processed_response['content']

            # Handle content-encoding header safely
            content_encoding = headers_dict.get("content-encoding", None)
            if content_encoding:
                content_encoding = content_encoding.replace("br", "")
                headers_dict["content-encoding"] = content_encoding.strip()
            
            # Return response with processed headers and content
            return Response(
                content=content,
                status_code=status_code,
                headers=headers_dict
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error forwarding request: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 