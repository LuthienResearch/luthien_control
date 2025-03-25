"""
FastAPI proxy server implementation for AI model API control.
Handles request forwarding while maintaining proper header management.
"""
from typing import Optional
import os
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
from httpx import Headers

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Change to INFO for production
logger = logging.getLogger(__name__)

class ProxyConfig(BaseModel):
    """Configuration for the proxy server."""
    target_url: str
    api_key: Optional[str] = None

app = FastAPI(title="Luthien Control Framework")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global configuration
config = ProxyConfig(
    target_url="https://api.openai.com",
    api_key=os.getenv("OPENAI_API_KEY")
)

def get_headers(request: Request) -> Headers:
    """
    Get headers for the proxy request, ensuring proper case-insensitive handling.
    Uses httpx.Headers for automatic case-insensitive header management.
    """
    headers = Headers(dict(request.headers))
    
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    
    headers.pop("host", None)
    headers.pop("content-length", None)
    
    return headers

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(request: Request, path: str):
    """
    Forward requests to the target API, preserving all original request properties.
    Handles header management and proper response forwarding.
    """
    target_url = f"{config.target_url}/v1/{path}"
    headers = get_headers(request)
    body = await request.body() if request.method in ["POST", "PUT"] else None

    # Log incoming Accept-Encoding header
    logger.debug(f"Incoming Accept-Encoding: {request.headers.get('accept-encoding')}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params
            )
            
            return Response(
                content=await response.aread(),
                status_code=response.status_code,
                headers=dict(response.headers)
            )
    except httpx.RequestError as e:
        logger.error(f"Error forwarding request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error forwarding request: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 