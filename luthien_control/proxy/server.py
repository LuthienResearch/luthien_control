"""
FastAPI proxy server implementation for AI model API control.
"""
from typing import Any, Dict, Optional
import os
import logging
from pathlib import Path
import brotli

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.datastructures import Headers

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log environment variable status (without exposing the key)
logger.debug(f"OPENAI_API_KEY is {'set' if os.getenv('OPENAI_API_KEY') else 'not set'}")

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
    logger.debug("Health check endpoint called")
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
    
    # Log request details
    logger.debug(f"Proxying {request.method} request to {target_url}")
    logger.debug(f"Headers: {headers}")
    if body:
        logger.debug(f"Body: {body}")
    
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
            
            # Log response details
            logger.debug(f"Received response with status {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            # Read response content once
            content = await response.aread()
            
            # Log response content for debugging
            logger.debug(f"Response content: {content}")

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
        logger.error(f"Error forwarding request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error forwarding request: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 