# Why Portkey Works but Luthien Fails with Cursor IDE

## The core compatibility difference

The fundamental difference lies in their architectural design philosophy. **Portkey AI Gateway** was built as a transparent forward proxy specifically for AI workloads, while **Luthien Control** was designed as a terminal proxy with AI Control policy enforcement. This architectural divergence creates multiple technical incompatibilities in the proxy chain.

## Critical technical incompatibilities

### Tool choice format mismatch causes immediate failures

The most immediate failure point is the **tool_choice parameter format incompatibility**. Cursor IDE sends function calling requests with `tool_choice: {"type": "auto"}`, following the newer OpenAI API format. However, Luthien Control expects the simplified `tool_choice: "auto"` format. This mismatch causes request validation failures, resulting in 400 Bad Request errors before the request even reaches OpenAI.

Portkey, by contrast, maintains exact OpenAI API format compatibility and preserves the request structure without modification, allowing Cursor's format to pass through unchanged.

### Authentication header conflicts break the proxy chain

**Luthien Control** implements its own authentication layer using `TEST_CLIENT_API_KEY` patterns, indicating it manages authentication rather than transparently forwarding it. In the proxy chain (`Client <-> Cursor <-> Luthien <-> OpenAI`), this creates authentication conflicts where Cursor's forwarded OpenAI API keys collide with Luthien's authentication mechanism.

**Portkey** uses a sophisticated header forwarding system with `x-portkey-forward-headers` that preserves all authentication headers. It accepts standard `Authorization: Bearer` headers and routes them appropriately without interference, maintaining the authentication context throughout the proxy chain.

### Request modification vs. transparent pass-through

**Luthien Control's** core functionality involves applying AI Control policies that modify requests and responses. This stateful behavior, backed by PostgreSQL logging, assumes direct client connections and doesn't account for pre-processed requests from upstream proxies like Cursor. The policy validation logic may reject or further modify already-transformed requests.

**Portkey** operates as a transparent proxy with minimal latency (<1ms overhead). While it adds enterprise features like observability and routing, it preserves the original request/response structure. Its forward-proxy architecture specifically handles client-initiated requests without breaking expectations.

### HTTP/2 support and streaming response handling

Cursor IDE requires **HTTP/2 support** for critical features like Cursor Tab and Inline Edit. The research indicates that FastAPI + Uvicorn setups (like Luthien) often have issues with HTTP/2 forwarding and connection management in proxy chains. Additionally, Luthien's policy application may interfere with streaming responses needed for real-time code completion.

**Portkey** provides native support for Server-Sent Events (SSE) streaming responses, maintaining compatibility with clients expecting OpenAI streaming format. It preserves the chunk structure and timing without buffering, essential for Cursor's real-time features.

### Header preservation and proxy chain awareness

**Luthien Control** lacks explicit proxy chain header preservation logic. FastAPI proxy implementations often don't properly handle proxy-specific headers like `X-Forwarded-*` or maintain custom headers through the chain. Cursor uses specialized headers like `x-ghost-mode` for privacy mode routing that must be preserved.

**Portkey's** header management system automatically preserves custom headers while adding its own headers non-destructively. The `x-portkey-forward-headers` array-based system ensures arbitrary headers pass through the proxy chain intact.

## Architectural assumptions that break compatibility

### Terminal proxy vs. middleware proxy design

**Luthien Control** assumes it's the final proxy before the API endpoint (`BACKEND_URL` configuration), implementing features appropriate for a terminal proxy:
- Stateful request tracking with database logging
- Policy enforcement and request transformation
- Direct authentication management
- No consideration for upstream proxy modifications

**Portkey** is designed for middleware operation:
- Stateless request handling
- Transparent operation mode
- Header and authentication preservation
- Explicit support for proxy chains

### Connection management differences

**Luthien's** FastAPI + Uvicorn setup typically assumes direct client connections without proxy-aware connection handling. Keep-alive and connection pooling mechanisms may not work correctly when requests come through Cursor's proxy.

**Portkey** implements proper connection pooling and state management for downstream services, maintaining request context across the proxy chain while handling connection management transparently.

## Why these differences matter for Cursor

Cursor IDE's proxy architecture has specific requirements:
1. **Exact OpenAI API format compliance** - Any deviation causes failures
2. **HTTP/2 protocol support** - Required for core IDE features
3. **Streaming response preservation** - Essential for real-time code completion
4. **Header forwarding integrity** - Custom headers must pass through unchanged
5. **Transparent authentication** - API keys must reach OpenAI unmodified

Portkey satisfies all these requirements through its transparent, forward-proxy design. Luthien Control's terminal proxy architecture with policy enforcement violates multiple requirements, making it incompatible with Cursor's proxy chain expectations.

## The path forward for Luthien Control

To achieve compatibility with Cursor IDE, Luthien Control would need:
1. **Tool choice format normalization** to handle both format variations
2. **Transparent proxy mode** that bypasses policy enforcement for specific requests
3. **Proxy chain header preservation** logic
4. **HTTP/2 support verification** and proper implementation
5. **Authentication forwarding** without local intervention
6. **Streaming response preservation** without buffering or modification

These changes would require significant architectural modifications to support transparent middleware operation while maintaining AI Control capabilities for direct client connections.