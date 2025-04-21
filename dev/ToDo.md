# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.

- [ ] Rework `dev/ProjectPlan.md`:
  - Reorganize sections based on current status and near-term goals (e.g., Testing Framework, Pipeline Refactor).
  - Clarify distinction between major phases and specific tasks.
  - Ensure alignment with overall project vision.

- [ ] Implement package-wide logging system

- [ ] security scan automation
- [ ] typehintchecking automation
- [ ] ruff automation
- [ ] client api check as policy (instead of in core)

- [ ] Migrate all datetime columns to use `TIMESTAMP WITH TIME ZONE` instead of the current `TIMESTAMP WITHOUT TIME ZONE`
  - All models would use true timezone-aware datetimes without stripping tzinfo
  - More robust for handling timezone-related edge cases and DST transitions
  - Requires careful migration to avoid breaking existing data and queries

- [X] Eliminate all traces of CONTROL_POLICIES
