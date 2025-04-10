# Policy Framework Refactor Plan (DB-Driven Instances)

This document outlines the plan to refactor the policy framework to use database-driven configuration, clearly distinguishing between policy *types* (classes) and policy *instances* (configured objects).

**Goal:** Load a single, top-level `ControlPolicy` instance identified by name (from settings) from the database. This instance can be simple or composite (like `CompoundPolicy`), and the loading mechanism should be flexible enough to accommodate future composite types.

## Core Concepts

1.  **Policy Type:** A Python class inheriting from `ControlPolicy` defining the logic (e.g., `ClientApiKeyAuthPolicy`, `CompoundPolicy`, future `ConditionalPolicy`).
2.  **Policy Instance:** A specific, named configuration of a Policy Type stored in the database. It links an instance name to a type (class path) and its specific configuration parameters.

## Implementation Steps

### 1. Database Schema (`policies` table)

-   Define a single `policies` table (via Pydantic model and migration).
-   **Columns:**
    -   `id`: PK (Integer)
    -   `name`: TEXT, UNIQUE, NOT NULL (Instance name, e.g., "RootApiFlow", "AuthPolicyForServiceX")
    -   `policy_class_path`: TEXT, NOT NULL (Path to the Python class defining the *type*, e.g., `luthien_control.control_policy.compound_policy.CompoundPolicy`)
    -   `config`: JSONB, NULLABLE (Stores *instance-specific configuration* needed by the `__init__` of the `policy_class_path` class)
    -   `is_active`: BOOLEAN, NOT NULL, DEFAULT true
    -   `description`: TEXT, NULLABLE
    -   `created_at`: TIMESTAMPTZ, NOT NULL, DEFAULT now()
    -   `updated_at`: TIMESTAMPTZ, NOT NULL, DEFAULT now()

### 2. Pydantic Models (`luthien_control/db/models.py`)

-   Define `PolicyBase` and `Policy(PolicyBase)` models matching the table schema.
-   `config` field should be `Optional[Dict[str, Any]]` or potentially `Optional[Json[Any]]`.
-   No `PolicyType` enum is needed.
-   No `PolicyMember` models are needed.

### 3. Instance Configuration (`config` JSON Field Examples)

-   **Simple Policy (e.g., `TimeoutPolicy`):** `{"timeout_seconds": 15}`
-   **`CompoundPolicy` Instance:** `{"member_policy_names": ["AuthInstanceName", "HeaderInstanceName", "LogInstanceName"]}` (Note: Uses instance *names*).
-   **Hypothetical `ConditionalPolicy` Instance:** `{"condition_param": "user_tier", "equals_value": "premium", "policy_if_true_name": "PremiumPolicyInstanceName", "policy_if_false_name": "StandardPolicyInstanceName"}`

### 4. Loading Logic (`luthien_control/db/crud.py`)

-   Implement `get_policy_config_by_name(name: str) -> Optional[Policy]`: Fetches the active `Policy` record by its unique instance `name`.
-   Implement `async def load_policy_instance(name: str, settings: Settings, http_client: httpx.AsyncClient, api_key_lookup: Callable, _visited_names: Optional[set[str]] = None) -> ControlPolicy`:
    -   Takes the instance `name` to load.
    -   Uses `get_policy_config_by_name` to fetch the `Policy` record.
    -   Handles `_visited_names` set for circular dependency detection based on *instance names*.
    -   Imports the class specified by `policy_config.policy_class_path`.
    -   Loads the `db_config = policy_config.config or {}`.
    -   Initializes `instance_args = {}`.
    -   **Inject common dependencies:** Check `__init__` signature for `settings`, `http_client`, `api_key_lookup` and add them to `instance_args` if present.
    -   **Handle Special Composite Types (using `issubclass` or direct type check):**
        -   **If `policy_class` is `CompoundPolicy`:**
            -   Get `member_names = db_config.get("member_policy_names", [])`.
            -   If not `member_names`, log warning.
            -   `loaded_members = []`
            -   For `member_name` in `member_names`:
                -   Recursively call `member_instance = await load_policy_instance(member_name, settings, ..., _visited_names.copy())`.
                -   Append `member_instance` to `loaded_members`.
            -   Add `instance_args["policies"] = loaded_members` (matching `CompoundPolicy.__init__`).
            -   Remove `"member_policy_names"` from `db_config` if it exists to prevent passing it as a direct argument.
        -   **If `policy_class` is `HypotheticalConditionalPolicy`:**
            -   Get `policy_true_name = db_config.get("policy_if_true_name")`.
            -   Get `policy_false_name = db_config.get("policy_if_false_name")`.
            -   Recursively load `policy_true_instance = await load_policy_instance(policy_true_name, ...)` (if name exists).
            -   Recursively load `policy_false_instance = await load_policy_instance(policy_false_name, ...)` (if name exists).
            -   Add `instance_args["policy_if_true"] = policy_true_instance`.
            -   Add `instance_args["policy_if_false"] = policy_false_instance`.
            -   Remove related names from `db_config`.
        -   *(Add blocks for other future composite types here)*
    -   **Inject remaining config:** Iterate through remaining `db_config` items. If a key matches an `__init__` parameter not already in `instance_args`, add it.
    -   **Parameter Validation:** Check `__init__` signature against `instance_args` for missing required parameters (excluding those with defaults and known dependencies).
    -   **Instantiate:** `instance = policy_class(**instance_args)`.
    -   Assign `instance.name = policy_config.name` for identification/logging.
    -   Return `instance`.

### 5. Dependency Injection (`luthien_control/dependencies.py`)

-   Keep the existing `get_control_policy` function (or similar).
-   It gets the `TOP_LEVEL_POLICY_NAME` from settings (defaulting to "root").
-   It calls `await crud.load_policy_instance(name=top_level_policy_name, settings=settings, http_client=client, api_key_lookup=lookup)`.
-   It returns the single loaded `ControlPolicy` instance.

### 6. `CompoundPolicy` (`luthien_control/control_policy/compound_policy.py`)

-   Ensure `__init__` accepts `policies: Sequence[ControlPolicy]` as the primary argument for receiving the loaded member instances.
-   The `name` parameter can still be used for logging if desired, potentially populated from the instance name during loading.

## Benefits

-   Clear separation of policy type definition (code) from configured instances (DB).
-   Database schema remains stable when adding new policy *types*.
-   Configuration for complex policies is contained within their specific instance `config`.
-   Loading logic centralizes the handling of different policy types during instantiation.
-   Flexibility to add new composite policy types (conditional, parallel, etc.) by implementing the class and adding a handler block in `load_policy_instance`. 