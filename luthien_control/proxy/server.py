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
from ..logging.file_logging import FileLogManager
from ..policies.manager import PolicyManager

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Set up logging
log_manager = FileLogManager(Path("logs"))
api_logger = log_manager.create_logger("api.log")

# Create policy manager
policy_manager = PolicyManager()

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
    # Create a Headers instance from the request headers
    header_dict = dict(request.headers)
    
    # Remove headers we don't want to forward
    header_dict.pop("host", None)
    header_dict.pop("content-length", None)
    
    # If no authorization header provided, use the server's API key
    if "authorization" not in {k.lower() for k in header_dict}:
        header_dict["Authorization"] = f"Bearer {config.api_key}"
    
    headers = Headers(header_dict)
    return headers

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

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