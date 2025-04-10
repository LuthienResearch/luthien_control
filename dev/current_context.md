# Current Task: Integrate DB-Driven Policy Loading

**Goal:** Update the dependency injection and request flow to use the new database-driven policy loading mechanism based on `load_policy_instance`.

**Status:** Completed implementation and testing of `Policy` models, `get_policy_config_by_name`, and `load_policy_instance` functions. Added `get_top_level_policy_name` to `Settings`.

**Next Steps:**
- Modify `dependencies.py`: Rename `get_control_policies` to `get_main_control_policy`, update return type and implementation to use `load_policy_instance` with `get_top_level_policy_name`. Remove old `load_control_policies`.
- Modify `orchestration.py`: Update `run_policy_flow` signature and logic to handle a single `main_policy`.
- Modify `server.py`: Update endpoint dependency to use `get_main_control_policy` and pass the single policy to `run_policy_flow`.
- Add tests for the updated dependency functions and potentially integration tests.
