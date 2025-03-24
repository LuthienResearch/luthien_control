"""
FastAPI proxy server implementation for AI model API control.
"""
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Luthien Control Framework")

class ProxyConfig(BaseModel):
    """Configuration for the proxy server."""
    target_url: str
    api_key: Optional[str] = None

# Global configuration - in production, this should be loaded from environment/config
config = ProxyConfig(
    target_url="https://api.openai.com/v1",
    api_key=None  # Should be loaded from environment in production
)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(request: Request, path: str):
    """
    Forward requests to the target API and log the interaction.
    """
    # Construct target URL
    target_url = f"{config.target_url}/{path}"
    
    # Forward headers
    headers = dict(request.headers)
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    
    # Forward body if present
    body = await request.body() if request.method in ["POST", "PUT"] else None
    
    # Log request (TODO: Implement proper logging)
    print(f"Proxying {request.method} request to {target_url}")
    
    # Forward request
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        
        # Log response (TODO: Implement proper logging)
        print(f"Received response with status {response.status_code}")
        
        # Stream response back to client
        return StreamingResponse(
            response.aiter_raw(),
            status_code=response.status_code,
            headers=dict(response.headers)
        ) 