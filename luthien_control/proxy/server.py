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

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Set up API logger
api_logger = APILogger(log_file="logs/api.log")

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

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(request: Request, path: str):
    """
    Forward requests to the target API and log the interaction.
    """
    # Construct target URL
    target_url = f"{config.target_url}/{path}"
    
    # Get headers
    headers = get_headers(request)
    
    # Forward body if present
    body = await request.body() if request.method in ["POST", "PUT"] else None
    
    # Log request details using our API logger
    api_logger.log_request(
        method=request.method,
        url=target_url,
        headers=dict(headers),
        body=body,
        query_params=dict(request.query_params)
    )
    
    try:
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

            # we need to remove "br" from the content-encoding header
            headers_dict = dict(response.headers)
            content_encoding = headers_dict.get("content-encoding", None)
            content_encoding = content_encoding.replace("br", "")
            headers_dict["content-encoding"] = content_encoding
            
            # Return response with original headers and content
            return Response(
                content=content,
                status_code=response.status_code,
                headers=headers_dict
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error forwarding request: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 