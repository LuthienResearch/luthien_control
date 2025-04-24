# Current Task: Refactor Dependencies Phase 2 - Debug Test Failures

**Goal:** Implement Phase 2 (Dependency Injection Container) of the plan defined in `dev/refactor_dependency_injection.md`.

**Overall Plan:**
1.  Define `DependencyContainer` (Done).
2.  Integrate into Lifespan (Done).
3.  Create Container Dependency (`get_dependencies`) (Done).
4.  Refactor Dependency Providers (`get_settings`, `get_http_client`, `get_db_session`) (Done).
5.  Refactor `get_main_control_policy` (Done).
6.  Refactor Core Logic (`load_policy_from_db`) (Done).
7.  Refactor Policy `apply` Signatures (`ClientApiKeyAuthPolicy`, `CompoundPolicy`) (Done).
8.  Update Base `ControlPolicy.apply` signature (Done - Step 11.5).
9.  Update API Route (`proxy/server.py`) signature and `apply` call (Done - Step 12).
10. Update Orchestration Function (`proxy/orchestration.py`) signature and `apply` call (Done - Step 12.5).
11. Refactor Tests (`tests/`) (Done - Step 13).
