# Project Plan: Luthien Control

*Note: This plan requires rework to better reflect current priorities and structure.*

## 1. Core Goal

To build an AI Control System (`luthien_control`) acting as an intelligent proxy server for OpenAI-compatible API endpoints. The system will intercept client requests and backend responses, apply user-defined control policies, log traffic, and eventually provide analysis tools for this data.

## 2. Initial Phase: Foundational Proxy & Logging

**Goal:** Build the foundational proxy server with basic pass-through functionality (client -> proxy -> backend -> proxy -> client) and implement robust logging of the traffic to PostgreSQL.

**Milestones/Checklist:**
- [X] Initialize project structure (`README.md`, `pyproject.toml`, directories).
- [X] Basic FastAPI application setup.
- [X] Implement core proxy endpoint that accepts OpenAI-compatible requests.
- [X] Configure target backend API endpoint (e.g., OpenAI) via environment variables.
- [X] Implement request forwarding logic to the target backend.
- [X] Implement response forwarding logic back to the client.
- [X] Define database schema for logging requests and responses.
- [X] Setup PostgreSQL connection using `asyncpg`.
- [ ] Implement asynchronous logging of request/response pairs to the database.
- [ ] Basic client authentication mechanism (TBD - e.g., static API key).
- [X] Unit tests for proxy logic.
- [X] Unit tests for database interaction/logging.
- [X] Basic integration tests for the end-to-end flow.

## 3. Future Phases (High-Level)

- [ ] Policy Engine Framework
- [ ] Basic Policy Implementations (e.g., redaction)
- [ ] Advanced Policy Features (e.g., verification, routing)
- [ ] Configuration Management for Policies
- [ ] Log Analysis Tools
- [ ] Enhanced Security & Authentication
- [ ] **Control Policy Application Framework:**
    - [X] Define `TransactionContext` object to carry state.
    - [X] Define `ControlPolicy` interface for composable processing steps.
    - [X] Define `ResponseBuilder` interface for final response generation.
    - [ ] Implement an endpoint which orchestrates context creation, policy execution, and response building.
    - [ ] Implement core policies (e.g., `RequestLoggingPolicy`, `SendBackendRequestPolicy`).
    - [ ] Switch `proxy_endpoint` to use this new system instead of the current logic
- [ ] **Enhanced E2E Testing Framework:**
    - [ ] Implement local proxy server management within test suite (e.g., `pytest-xprocess`).
    - [ ] Configure test target selection (local vs. deployed) via `pytest` arguments/fixtures.
    - [ ] Develop core E2E tests runnable against both targets.
    - [ ] Integrate tests into deployment verification workflow.
