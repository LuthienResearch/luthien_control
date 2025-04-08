# Luthien Control: Request Processing Framework

**Status:** Proposed

**Goal:** Define a modular, composable framework for processing client requests within Luthien Control. This framework replaces the previous monolithic approach in `luthien_control.proxy.server.proxy_endpoint`, improving maintainability, testability, and flexibility. It is designed to be agnostic about whether or how backend services are called during processing.

## Core Concepts

### 1. Transaction Context (`TransactionContext`)

This object carries the state throughout the processing flow. It is passed sequentially between processors. Key components include:

*   `transaction_id: str`: A unique identifier for the transaction.
*   `request: Optional[httpx.Request]`: The evolving *outgoing* request being prepared for or sent to a backend service.
*   `response: Optional[httpx.Response]`: The evolving response, potentially from a backend or constructed internally.
*   `data: Dict[Any, Any]`: A flexible dictionary for processors to store and retrieve arbitrary data (e.g., policy decisions, intermediate results).

### 2. Control Processor Interface (`ControlProcessor`)

The fundamental unit of work. Processors are composable, allowing complex workflows to be built from smaller, focused units. Each processor implements a method with the following signature:

`async def process(self, context: TransactionContext) -> TransactionContext`

Processors read from, act upon, and update the `TransactionContext`. They may raise exceptions to halt processing.

### 3. Response Builder Interface (`ResponseBuilder`)

Responsible for the final conversion of the processed `TransactionContext` into the client-facing `fastapi.Response`. It implements a method with the signature:

`def build_response(self, context: TransactionContext) -> fastapi.Response`

### 4. Orchestration (`proxy_endpoint`)

The main endpoint (`luthien_control.proxy.server.proxy_endpoint`) coordinates the flow:

1.  Receives the incoming `fastapi.Request`.
2.  Generates a `transaction_id`.
3.  Initializes the `TransactionContext`.
4.  Passes the context to the main `ControlProcessor` (which could be pre-instantiated).
5.  Passes the resulting context to the `ResponseBuilder`.
6.  Returns the final `fastapi.Response` to the client.
    Error handling is applied around the processor execution.

### 5. Concrete Processors (Examples)

Individual classes implementing `ControlProcessor`. Each focuses on a specific task:

*   `ApplyRequestPolicyProcessor`: Runs request-side policies, potentially modifying `context.data` or `context.current_request`, or raising `PolicyViolationError`.
*   `BuildBackendRequestProcessor`: Constructs `context.current_request` based on context state.
*   `SendBackendRequestProcessor`: Sends `context.current_request` using `httpx`, stores the `httpx.Response` in `context.current_response`. Handles `httpx` errors, potentially raising `BackendRequestError`.
*   `ApplyResponsePolicyProcessor`: Runs response-side policies based on `context.current_response`, potentially modifying it or raising errors.
*   ... other processors for logging, header manipulation, caching, etc.

This architecture provides a flexible foundation for adding or modifying processing logic without altering the core framework. 