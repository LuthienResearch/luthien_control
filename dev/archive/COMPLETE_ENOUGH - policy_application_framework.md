# Luthien Control: Control Policy Application Framework

**Status:** Proposed

**Goal:** Define a modular, composable framework for applying control policies to requests and responses passing through the proxy server. This framework replaces the previous monolithic approach in `luthien_control.proxy.server.proxy_endpoint`, improving maintainability, testability, and flexibility. It is designed to be agnostic about whether or how backend services are called during processing.

## Core Concepts

### 1. Transaction Context (`TransactionContext`)

This object carries the state throughout the policy processing flow. It is passed (typically sequentially) between control policies. Key components include:

* `transaction_id: str`: A unique identifier for the transaction.
* `request: Optional[httpx.Request]`: The evolving *outgoing* request, typically (but not necessarily) to be sent to a backend service.
* `response: Optional[httpx.Response]`: The evolving response, potentially from a backend, modified based on the backend, or constructed internally.
* `data: Dict[Any, Any]`: A flexible dictionary for control policies to store and retrieve arbitrary data (e.g., policy decisions, intermediate results).

Note that at any given point either the request or response may be missing entirely (e.g. it's possible to define flows that only attend to responses or requests). There is a case to be made for keeping these separate, but after experimenting with several approaches keeping everything under the common umbrella of "TransactionContext" seems like the most straightforward, flexible approach.

### 2. Control Policy Interface (`ControlPolicy`)

The fundamental unit of work. Policies are composable, allowing complex workflows to be built from smaller, focused units. Each policy implements a method with the following signature:

`async def apply(self, context: TransactionContext) -> TransactionContext`

Policies read from, act upon, and update the `TransactionContext`. They may raise exceptions to halt further policy applications.

### 3. Response Builder Interface (`ResponseBuilder`)

Responsible for the final conversion of the processed `TransactionContext` into the client-facing `fastapi.Response`. It implements a method with the signature:

`def build_response(self, context: TransactionContext) -> fastapi.Response`

### 4. Orchestration (`proxy_endpoint`)

The main endpoint (`luthien_control.proxy.server.proxy_endpoint`) coordinates the flow:

1. Receives the incoming `fastapi.Request`.
2. Generates a `transaction_id`.
3. Initializes the `TransactionContext`.
4. Passes the context to the main `ControlPolicy` (which could be pre-instantiated).
5. Passes the resulting context to the `ResponseBuilder`.
6. Returns the final `fastapi.Response` to the client.
    Error handling is applied around the policy execution.

### 5. Concrete Policies (Examples)

Individual classes implementing `ControlPolicy`. Each focuses on a specific task:

* `SendBackendRequestPolicy`: Sends `context.request` using `httpx`, stores the `httpx.Response` in `context.response`. Handles `httpx` errors, potentially raising `BackendRequestError`.
* `RequestLoggingPolicy`: Logs details from the `context.request` (e.g., headers, method, URL) at the start or end of processing.
* `AddApiKeyPolicy`: Retrieves an API key (e.g., from configuration or `context.data`) and adds it as a header (e.g., `Authorization` or `X-Api-Key`) to `context.request`.
* `StripSecretsPolicy`: Removes sensitive headers or data from `context.request` before it's sent to the backend, based on configuration.
* `RephraseRequestPolicy`: Modifies the content or structure of `context.request` based on specified rules or an external model call (e.g., simplifying prompts, adding context). Might store the original request in `context.data`.
* `RephraseResponsePolicy`: Modifies the content or structure of `context.response` based on specified rules or an external model call (e.g., summarizing, filtering, changing format).
* `BackendSamplingPolicy`: Executes the backend request (similar to `SendBackendRequestPolicy`) N times. Stores all N responses (e.g., in `context.data['backend_samples']`).
* `RankAndSelectResponsePolicy`: Evaluates multiple responses (e.g., those stored by `BackendSamplingPolicy` in `context.data['backend_samples']`) using a defined heuristic or model. Selects the best response and sets it as the final `context.response`.

This architecture provides a flexible foundation for adding or modifying processing logic.
