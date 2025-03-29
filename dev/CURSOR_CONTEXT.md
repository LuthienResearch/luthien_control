# Current Working Context
[Updated March 29, 2024 11:00]

## Implementation Phase
- Development Workflow Improvement
- Specific component: Pre-commit hooks configuration (`.pre-commit-config.yaml`) and documentation (`README.md`).

## Working State
- **Pre-commit Hooks:** `ruff-format` and `trailing-whitespace` hooks removed from `.pre-commit-config.yaml`. Remaining hooks (`ruff check --fix`, `bandit`, `mypy`) focus on checking code quality, security, and types.
- **Documentation:** `README.md` updated to reflect the new commit workflow, emphasizing developer responsibility for formatting code *before* staging (`git add`).
- **Goal:** Smoother, faster commit process by eliminating conflicts from auto-formatting hooks modifying files during commit.

## Current Blockers
- None. The planned changes to pre-commit configuration and documentation are complete.

## Next Steps
1. **Test:** Attempt a commit with the new configuration to verify the workflow functions as expected (no formatting conflicts, checking hooks run correctly).
2. **Monitor:** Observe the developer experience with this new workflow over time.
3. **Address Future Issues:** If `ruff check --fix` causes similar modification conflicts, consider removing the `--fix` flag and making linting purely a checking step as well.

## Data Model (Current Draft)
### Comm Table
- id: uuid
- source: text
- destination: text
- type: enum (request, response)
- timestamp: timestamp
- content: jsonb
- endpoint: text
- arguments: jsonb
- trigger: jsonb

### CommRelationship Table
- id: uuid
- from_comm_id: uuid
- to_comm_id: uuid
- relationship_type: text
- meta_info: jsonb  # Note: Renamed from metadata to avoid SQLAlchemy conflict
