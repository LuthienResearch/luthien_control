# Fixing the ASGI protocol violation in Luthien Control

NOTE: We ended up just deleting the middleware

The streaming response error in Luthien Control stems from a well-documented conflict between Starlette's BaseHTTPMiddleware and StreamingResponse functionality. The error "RuntimeError: Unexpected message received: http.request" occurs when middleware attempts to read the request body while the streaming response tries to use the same ASGI receive channel - a violation of the ASGI protocol introduced in Starlette v0.28.0.

## Root cause analysis reveals a middleware conflict

The issue arises from a fundamental incompatibility in how BaseHTTPMiddleware manages the ASGI message flow. When middleware reads the request body using `await request.body()`, `request.json()`, or similar methods, it consumes messages from the ASGI receive channel. Later, when StreamingResponse attempts to listen for client disconnections by calling `receive()`, it unexpectedly receives `http.request` messages that BaseHTTPMiddleware's `wrapped_receive` function doesn't expect at this stage of the response cycle.

In the Luthien Control codebase, this likely occurs in the AI Control policy enforcement middleware. As a proxy server that sits between clients and AI backends, Luthien Control probably inspects request bodies to enforce policies before forwarding requests. This inspection pattern conflicts with the streaming response mechanism when forwarding responses from OpenAI or other backends.

## The quickest fixes avoid extensive refactoring

### Remove request body reading in middleware
The simplest immediate fix involves removing or conditionalizing request body reading in your middleware. If your policy enforcement doesn't require inspecting the body for streaming endpoints, modify the middleware:

```python
@app.middleware("http")
async def policy_middleware(request: Request, call_next):
    # Skip body reading for streaming endpoints
    if request.url.path.endswith("/stream") or "stream" in request.url.path:
        return await call_next(request)
    
    # Only read body for non-streaming endpoints
    body = await request.body()
    # Policy enforcement logic here
    response = await call_next(request)
    return response
```

### Convert to pure ASGI middleware
For a more robust solution that maintains full functionality, replace BaseHTTPMiddleware with pure ASGI middleware. This approach provides complete control over the ASGI protocol:

```python
class PolicyASGIMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Your policy logic here without body reading conflicts
        await self.app(scope, receive, send)

app.add_middleware(PolicyASGIMiddleware)
```

### Use background tasks for logging
If your middleware primarily logs requests and responses, move this functionality to background tasks:

```python
from fastapi import BackgroundTasks

async def log_request_response(request_data, response_data):
    # Logging logic here
    pass

@app.post("/proxy/{path:path}")
async def proxy_endpoint(path: str, request: Request, background_tasks: BackgroundTasks):
    request_body = await request.body()
    # Forward to backend and get streaming response
    backend_response = await forward_to_backend(path, request_body)
    
    # Log asynchronously without blocking streaming
    background_tasks.add_task(log_request_response, request_body, {"path": path})
    
    return StreamingResponse(backend_response.aiter_content())
```

## Implementation strategy maximizes stability

Given that the OpenAI client streaming works correctly (9 chunks) and FastAPI StreamingResponse creation succeeds, the issue is isolated to the middleware layer. The recommended approach:

1. **Identify all middleware** in your application, particularly in the `proxy/` directory
2. **Locate request body reading** - search for `request.body()`, `request.json()`, or `request.form()`
3. **Apply the conditional fix** first as it requires minimal changes
4. **Test streaming endpoints** to verify the fix works
5. **Consider migrating** to pure ASGI middleware for long-term stability

## Version considerations and known workarounds

This issue affects Starlette 0.28.0+ and FastAPI 0.107.0+. While downgrading Starlette below 0.28.0 would resolve the issue, this approach sacrifices security updates and isn't recommended. The community has extensively documented this problem, with multiple production-tested solutions available.

For the Luthien Control codebase specifically, the AI proxy nature of the application makes the conditional middleware approach particularly suitable. You can maintain full policy enforcement for regular endpoints while allowing streaming responses to pass through unimpeded.

## Conclusion

The streaming response issue in Luthien Control represents a common ASGI protocol violation that occurs when BaseHTTPMiddleware interferes with StreamingResponse. Rather than the extensive refactoring suggested in the fix plan, implement one of these targeted solutions that address the root cause directly. The conditional middleware approach offers the quickest path to resolution while maintaining your existing architecture.