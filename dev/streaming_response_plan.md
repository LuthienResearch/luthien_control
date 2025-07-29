# Streaming Response Implementation Plan

## Overview
This document outlines the plan to make the Luthien Control framework compatible with streaming responses. Currently, the framework processes requests through a policy chain and returns complete responses. We need to extend it to handle streaming responses where multiple response chunks are sent for a single request.

## Current Architecture

### Request Flow
1. **Entry Point**: `proxy/orchestration.py:run_policy_flow()`
   - Initializes transaction based on request type (OpenAI or raw)
   - Applies main policy chain
   - Builds final response from transaction

2. **Policy Application**: `ControlPolicy.apply()`
   - Each policy transforms the transaction
   - Policies can generate responses
   - Other policies may act on generated responses

3. **Backend Communication**: `SendBackendRequestPolicy`
   - Handles actual API calls
   - Currently detects streaming but stores in `transaction.data`
   - No proper streaming response handling

4. **Response Building**
   - Expects complete responses in `transaction.openai_response.payload`
   - Converts to FastAPI responses

### Current Limitations
- No streaming iterator support in Transaction model
- Orchestration expects complete responses
- Policies can't handle streaming data
- No streaming response builders

## Implementation Plan

### Phase 1: Core Streaming Infrastructure

#### 1.1 Streaming Response Types
**Status**: [x] Completed

Create new types to represent streaming responses:
- [x] Create `luthien_control/core/streaming_response.py`
  - `StreamingResponseIterator`: Base class for streaming iterators
  - `OpenAIStreamingIterator`: Wrapper for OpenAI async streams
  - `RawStreamingIterator`: Wrapper for raw HTTP streams
  - `ChunkedTextIterator`: For testing and text chunking

- [x] Update `luthien_control/core/response.py`
  - Add `streaming_iterator: Optional[StreamingResponseIterator]` field
  - Add `is_streaming: bool` property

- [x] Update `luthien_control/core/raw_response.py`
  - Add `streaming_iterator: Optional[StreamingResponseIterator]` field
  - Add `is_streaming: bool` property

#### 1.2 Transaction Model Updates
**Status**: [x] Completed

- [x] Update `luthien_control/core/transaction.py`
  - Add `is_streaming` property that checks response objects
  - Ensure validation allows streaming responses without payload
  - Add type annotations for streaming support

#### 1.3 Streaming Utilities
**Status**: [x] Completed

- [x] Create `luthien_control/utils/streaming.py`
  - Chunk formatting utilities (SSE, JSON streaming)
  - Stream error handling helpers
  - Buffer management for policies
  - StreamingBuffer class for peek/replay functionality

### Phase 2: Policy Chain Streaming Support

#### 2.1 Streaming-Aware Policy Interface
**Status**: [ ] Partially Complete

- [ ] Create `luthien_control/control_policy/streaming_policy.py`
  - `StreamingControlPolicy`: Base class for stream-aware policies
  - Methods for chunk processing
  - Buffering capabilities for policies needing complete data

- [x] Update existing policies for streaming compatibility:
  - [x] `SendBackendRequestPolicy`: Properly set streaming iterators
  - [ ] `TransactionContextLoggingPolicy`: Handle streaming objects
  - [ ] Other policies: Pass through streaming responses

#### 2.2 SendBackendRequestPolicy Updates
**Status**: [x] Completed

- [x] Modify `_handle_openai_request()`:
  - Create `OpenAIStreamingIterator` for streaming responses
  - Set `transaction.openai_response.streaming_iterator`
  - Remove temporary `transaction.data` storage

- [x] Add streaming support for raw requests:
  - Handle streaming HTTP responses (detect via Accept header)
  - Create appropriate streaming iterators
  - Support both streaming and non-streaming responses

### Phase 3: Response Building & Delivery

#### 3.1 Streaming Response Builders
**Status**: [x] Completed

- [x] Create `luthien_control/api/openai_chat_completions/streaming_response.py`
  - SSE formatter for OpenAI streaming
  - Convert streaming iterator to FastAPI StreamingResponse
  - Handle errors during streaming
  - Proper SSE termination with `[DONE]` event

- [x] Update `proxy/orchestration.py`:
  - Detect streaming transactions
  - Route to streaming response builders
  - Return FastAPI StreamingResponse
  - Support both OpenAI and raw streaming responses

#### 3.2 Error Handling
**Status**: [ ] Partially Complete

- [x] Streaming error recovery (basic SSE error formatting)
- [ ] Client disconnection handling
- [ ] Policy error propagation in streams

### Phase 4: Testing & Validation

#### 4.1 Unit Tests
**Status**: [x] Completed

- [x] Test streaming response types
- [x] Test streaming iterators
- [x] Test policy streaming compatibility
- [x] Test response builders

#### 4.2 Integration Tests
**Status**: [ ] Not Started

- [ ] Policy chain with streaming
- [ ] End-to-end streaming flows
- [ ] Error scenarios
- [ ] Mixed streaming/non-streaming policies

#### 4.3 E2E Tests
**Status**: [ ] Not Started

- [ ] Real OpenAI streaming endpoints
- [ ] Client streaming consumption
- [ ] Performance testing

## Implementation Notes

### Design Decisions
- **Backward Compatibility**: All changes must maintain compatibility with existing non-streaming flows
- **Policy Transparency**: Most policies should work unchanged with streaming responses
- **Error Recovery**: Streaming errors should be handled gracefully without breaking the stream

### Key Challenges
1. **Policy Buffering**: Some policies may need complete responses (e.g., for validation)
2. **Error Propagation**: How to handle errors mid-stream
3. **Testing**: Mocking streaming responses effectively
4. **Performance**: Ensuring minimal overhead for streaming

### Open Questions
- [ ] Should policies be able to modify streaming chunks?
- [ ] How to handle timeouts in streaming contexts?
- [ ] Should we support different streaming formats (SSE, JSONL, etc.)?
- [ ] How to handle metrics/logging for streaming responses?

## Progress Tracking

### Completed
- [x] Architecture analysis
- [x] Initial planning
- [x] Document creation
- [x] Core streaming infrastructure (Phase 1)
- [x] SendBackendRequestPolicy streaming support
- [x] Streaming response builders (Phase 3.1)
- [x] Unit tests for streaming functionality

### In Progress
- [ ] Streaming-aware policy base classes
- [ ] Update remaining policies for streaming compatibility
- [ ] Integration and E2E tests

### Blocked
- [ ] None currently

## Adaptations & Changes
_This section will track any deviations from the original plan as implementation progresses._

### Date: 2025-07-29
- **Change**: Used Pydantic model config instead of Config class
  - **Reason**: Pydantic v2 uses model_config dict instead of inner Config class
  - **Impact**: Updated all StreamingResponseIterator subclasses

- **Change**: Added `iter_cache` field to RawStreamingIterator
  - **Reason**: Need to store the iterator to avoid recreating it on each __anext__ call
  - **Impact**: Added excluded field to model

- **Change**: Removed use of `transaction.data` for storing streams
  - **Reason**: Better to use proper response fields for type safety
  - **Impact**: Updated SendBackendRequestPolicy and related tests

- **Change**: Added `ChunkedTextIterator` for testing
  - **Reason**: Needed a simple iterator for unit tests
  - **Impact**: Additional test utility class