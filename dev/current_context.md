# Development Plan and Progress

## Current Task: Resolve Pyright Errors

**Overall Goal:** Eliminate all 52 errors reported by `pyright luthien_control`.

**Plan of Action (Prioritized):**

1.  [ ] **Fix `ControlPolicy` attribute errors in `db/control_policy_crud.py` (Category 2 from pyright output):**
    *   Investigate imports and type definitions related to `ControlPolicy`.
    *   Ensure the SQLModel version of `ControlPolicy` is used where DB attributes are accessed.
2.  [ ] **Address `SerializablePrimitive` / `SerializableDict` mismatches (Category 1):**
    *   Review definitions of `Serializable` types.
    *   Examine function signatures and assignments.
    *   Ensure type conversions/checks are in place.
3.  [ ] **Resolve SQLAlchemy `where` clause errors (Category 3):**
    *   Modify `where()` clauses to use proper column expressions.
4.  [ ] **Handle incompatible overrides and variable type issues (Category 4):**
    *   Refactor class/instance variables or method signatures to ensure compatibility.
5.  [ ] **Clean up miscellaneous attribute access issues (Category 5):**
    *   Add type checks, remove redundant calls, ensure correct object usage.

**Current Step:** Created `dev/pyright_fixes_plan.md`.

**Next Step:** Begin investigation of item 1: `ControlPolicy` attribute errors in `luthien_control/db/control_policy_crud.py`.
