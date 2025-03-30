import httpx
from fastapi import Request, HTTPException

def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Dependency function to get the shared httpx.AsyncClient from application state.

    Raises:
        HTTPException: If the client is not found in the application state.
    """
    print(f"---> request.app ID in dependency: {id(request.app)} <---") # DEBUG PRINT
    client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if client is None:
        # This indicates a critical setup error if the lifespan manager didn't run
        # or didn't set the state correctly.
        print("!!! CRITICAL ERROR: httpx.AsyncClient not found in request.app.state")
        raise HTTPException(
            status_code=500,
            detail="Internal server error: HTTP client not available."
        )
    return client 