# Current Task
## Implement Enhanced E2E Testing Framework
 - Status: Starting
 - Motivation: To establish a robust testing harness before undertaking the major pipeline architecture refactor (see `docs/designs/pipeline_architecture.md`). This involves running the same E2E tests against both local and deployed instances.
 - Goal: Enhance the testing setup to allow running E2E tests against both a locally managed proxy instance and the deployed Fly.io instance. See also `dev/ProjectPlan.md`.
 - Immediate Next Steps:
    1. Integrate `pytest-xprocess` (or similar) to manage the lifecycle of the local Luthien Control proxy server within the pytest execution flow.
    2. Implement test target selection (local vs. fly) using pytest fixtures and command-line arguments (e.g., `pytest --target=local`).
