# Current Task: COMPLETED

**Goal:** Refactor `luthien_control/db/sqlmodel_crud.py` to align policy CRUD operations with the new loader approach.

**Outcome:**
- Removed redundant policy config CRUD functions.
- Updated `save_policy_to_db` (formerly `create_policy`) and `update_policy` error handling for `IntegrityError` and `SQLAlchemyError`, ensuring `IntegrityError` is re-raised.
- Updated `tests/db/test_sqlmodel_crud.py` to match the new error handling.
- All tests related to the module pass. Development logs (`development_log.md`, `current_context.md`) updated.

**Next Steps:** Commit the changes.
