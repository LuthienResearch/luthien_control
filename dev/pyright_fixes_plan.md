# Pyright Error Resolution Plan

This document outlines the plan to address the 52 errors identified by `pyright` in the `luthien_control` package.

## Prioritization Strategy:

The errors will be addressed in the following order based on their likely impact and interconnectedness:

1.  **Fix `ControlPolicy` attribute errors in `db/control_policy_crud.py` (Category 2 from pyright output):**
    *   **Issue:** Numerous errors like `Cannot access attribute "id" for class "ControlPolicy"`. This suggests a potential mismatch between the expected `ControlPolicy` type (e.g., base Pydantic model) and the actual type being used (e.g., SQLModel version which *should* have DB attributes).
    *   **Action:** Investigate imports and type definitions related to `ControlPolicy` in `luthien_control/db/control_policy_crud.py`. Ensure the SQLModel version of `ControlPolicy` (likely from `luthien_control.db.sqlmodel_models`) is used where database attributes are accessed. This might also resolve some related return type issues.

2.  **Address `SerializablePrimitive` / `SerializableDict` mismatches (Category 1):**
    *   **Issue:** Widespread type mismatches involving these custom types, particularly in `control_policy` modules. Often occurs when a `float`, `None`, or other primitive is used where a `dict` or `str` (or a more specific structure) is expected, especially during (de)serialization.
    *   **Action:**
        *   Review the definitions of `SerializablePrimitive`, `SerializableDict`, `SerializableType`, etc. (likely in `luthien_control.utils.types` or similar).
        *   Examine function signatures and assignments where these types are used.
        *   Ensure that type conversions or checks are in place when moving between general types (like `SerializablePrimitive`) and more specific expected types (e.g., ensuring a value is a `str` before assigning it to a `str` field). Pay close attention to `.get()` methods on dictionaries that might return `None` or a different type than expected.

3.  **Resolve SQLAlchemy `where` clause errors (Category 3):**
    *   **Issue:** Errors like `Argument of type "bool" cannot be assigned to parameter "whereclause" of type "_ColumnExpressionArgument[bool]"` in `db/client_api_key_crud.py` and `db/control_policy_crud.py`.
    *   **Action:** Modify the `where()` clauses in SQLAlchemy queries to use proper column expressions (e.g., `MyModel.field == value`) instead of raw boolean values if that's the cause.

4.  **Handle incompatible overrides and variable type issues (Category 4):**
    *   **Issue:**
        *   `control_policy/conditions/comparisons.py`: Class variable `type` overriding instance variable, and incompatible `from_serialized` method signature.
        *   `control_policy/send_backend_request.py`: `name` attribute overriding with an incompatible type.
    *   **Action:** Refactor the class variable or instance variable in `comparisons.py` to avoid the name collision or ensure compatibility. Adjust the `from_serialized` method signature. For `send_backend_request.py`, ensure the `name` attribute's type is consistent with the base class or use a different name.

5.  **Clean up miscellaneous attribute access issues (Category 5):**
    *   **Issue:**
        *   `branching_policy.py`: `Cannot access attribute "items" for class "str"/"float"/etc.` (attempting dict operations on non-dict types).
        *   `send_backend_request.py`: `Cannot access attribute "encode" for class "bytes"` (bytes are already encoded) and `"headers" is not a known attribute of "None"` (optional access needed).
        *   `control_policy/loader.py`: ` "__getitem__" method not defined on type "SerializedPolicy"`.
    *   **Action:**
        *   For `branching_policy.py`, add type checks before attempting `.items()`.
        *   For `send_backend_request.py`, remove the redundant `.encode()` call and add a check for `None` before accessing `headers`.
        *   For `loader.py`, ensure `SerializedPolicy` is a `Mapping` if `__getitem__` is intended, or refactor to use attribute access/methods if it's an object.

## Next Steps:

Start with item 1: Investigating `ControlPolicy` attribute errors in `db/control_policy_crud.py`. 