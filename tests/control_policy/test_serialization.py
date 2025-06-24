from luthien_control.control_policy.serialization import SerializableDict, SerializedPolicy


def test_serialized_policy_dataclass():
    """Verify that the SerializedPolicy dataclass can be instantiated correctly."""
    policy_type = "MyPolicy"
    policy_config: SerializableDict = {
        "param1": "value1",
        "param2": 123,
        "param3": True,
        "nested": {"key": "nested_value"},
    }

    serialized_policy = SerializedPolicy(type=policy_type, config=policy_config)

    assert serialized_policy.type == policy_type
    assert serialized_policy.config == policy_config
    assert serialized_policy.config["param1"] == "value1"
    assert isinstance(serialized_policy.config["nested"], dict)
    assert serialized_policy.config["nested"]["key"] == "nested_value"
