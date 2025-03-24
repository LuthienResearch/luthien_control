---
description: 
globs: 
alwaysApply: true
---
# AI Control Framework Implementation Plan (MVP)

## Phase 0: Setup
 - Initialize git
 - Setup poetry python env following best practices
 - Create a README.md
 - Initialize git repo under LuthienResearch org and push

## Phase 1: Transparent Proxy
- Develop a basic HTTP proxy server using FastAPI that captures all traffic
- Implement logging of complete request/response pairs for analysis
- Implement authentication as part of the proxy (e.g. server has the actual API key)
- Deploy in a test environment and collect data on API usage patterns
- Document all endpoints, parameters, and response structures observed

## Phase 2: Control Engine Development
- Implement a framework to implement arbitrary policies on requests/responses (these policies may, on any given request/response, pass it through, block it, or change it)
- Create test suite with sample policies for common scenarios
- Implement request/response transformation capabilities