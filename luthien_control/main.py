from fastapi import FastAPI

app = FastAPI(
    title="Luthien Control",
    description="An intelligent proxy server for AI APIs.",
    version="0.1.0", # Consider deriving from pyproject.toml later
)

@app.get("/health", tags=["General"], status_code=200)
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}

# Further endpoints (like the main proxy endpoint) will be added here.

# To run the server (from the project root directory):
# uvicorn luthien_control.main:app --reload
