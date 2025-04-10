# Current Task: Policy Serialization Implementation

## Short Description of Current Task
Implement and test the `serialize_config` method on `ControlPolicy` and its subclasses to enable saving policy configurations.

- Status: Complete
- Major changes made:
    - Added abstract `serialize_config` to `ControlPolicy` interface.
    - Implemented `serialize_config` in all concrete policy classes.
    - Created `tests/control_policy/test_serialization.py` with round-trip tests.
    - Added required mock fixtures (`mock_settings`, `mock_http_client`, `mock_api_key_lookup`) to `tests/conftest.py`.
    - Fixed test failures related to missing fixtures and incorrect mock assertions.
- Follow-up tasks, if any (Excluding git commit/push/etc):
    - None immediate. Consider implementing DB save logic (`save_policy_instance`?) in a future task if needed.
