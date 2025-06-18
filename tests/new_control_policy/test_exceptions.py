import pytest
from luthien_control.new_control_policy.exceptions import (
    ApiKeyNotFoundError,
    ClientAuthenticationError,
    ClientAuthenticationNotFoundError,
    ControlPolicyError,
    LeakedApiKeyError,
    NoRequestError,
    PolicyLoadError,
)


def test_control_policy_error_base():
    """Test basic raising and attribute setting for ControlPolicyError."""
    message = "Base policy error"
    policy_name = "TestPolicy"
    status_code = 500
    detail = "Detailed message"

    with pytest.raises(ControlPolicyError) as exc_info:
        raise ControlPolicyError(message, policy_name=policy_name, status_code=status_code, detail=detail)

    assert str(exc_info.value) == message
    assert exc_info.value.policy_name == policy_name
    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail == detail


def test_control_policy_error_detail_fallback():
    """Test that detail falls back to the first arg if not provided."""
    message = "Detail fallback test"
    with pytest.raises(ControlPolicyError) as exc_info:
        raise ControlPolicyError(message)
    assert exc_info.value.detail == message


def test_control_policy_error_no_detail():
    """Test that detail is None if no args and no detail kwarg."""
    with pytest.raises(ControlPolicyError) as exc_info:
        raise ControlPolicyError(policy_name="NoDetailPolicy")
    assert exc_info.value.detail is None


def test_policy_load_error():
    """Test raising PolicyLoadError."""
    message = "Failed to load policy"
    policy_name = "BadPolicy"
    with pytest.raises(PolicyLoadError) as exc_info:
        raise PolicyLoadError(message, policy_name=policy_name)

    assert issubclass(PolicyLoadError, ValueError)
    assert issubclass(PolicyLoadError, ControlPolicyError)
    assert str(exc_info.value) == message
    assert exc_info.value.policy_name == policy_name
    assert exc_info.value.detail == message  # Falls back to arg


def test_api_key_not_found_error():
    """Test raising ApiKeyNotFoundError."""
    message = "API key missing"
    with pytest.raises(ApiKeyNotFoundError) as exc_info:
        raise ApiKeyNotFoundError(message)

    assert issubclass(ApiKeyNotFoundError, ControlPolicyError)
    assert str(exc_info.value) == message
    assert exc_info.value.detail == message  # Falls back to arg


def test_no_request_error():
    """Test raising NoRequestError."""
    message = "Request object not found"
    with pytest.raises(NoRequestError) as exc_info:
        raise NoRequestError(message)

    assert issubclass(NoRequestError, ControlPolicyError)
    assert str(exc_info.value) == message
    assert exc_info.value.detail == message  # Falls back to arg


def test_client_authentication_error():
    """Test raising ClientAuthenticationError."""
    detail = "Invalid client key"
    status_code = 403
    with pytest.raises(ClientAuthenticationError) as exc_info:
        raise ClientAuthenticationError(detail=detail, status_code=status_code)

    assert issubclass(ClientAuthenticationError, ControlPolicyError)
    # Note: ControlPolicyError.__init__ is called with detail as the only arg
    assert str(exc_info.value) == detail
    assert exc_info.value.detail == detail
    assert exc_info.value.status_code == status_code


def test_client_authentication_not_found_error():
    """Test raising ClientAuthenticationNotFoundError."""
    detail = "Client key header missing"
    status_code = 401  # Default should be used if not provided
    with pytest.raises(ClientAuthenticationNotFoundError) as exc_info:
        raise ClientAuthenticationNotFoundError(detail=detail)

    assert issubclass(ClientAuthenticationNotFoundError, ControlPolicyError)
    # Note: ControlPolicyError.__init__ is called with detail as the only arg
    assert str(exc_info.value) == detail
    assert exc_info.value.detail == detail
    assert exc_info.value.status_code == status_code


def test_leaked_api_key_error():
    """Test raising LeakedApiKeyError."""
    detail = "Leaked API key detected in request"
    status_code = 403  # Default should be used if not provided
    with pytest.raises(LeakedApiKeyError) as exc_info:
        raise LeakedApiKeyError(detail=detail)

    assert issubclass(LeakedApiKeyError, ControlPolicyError)
    assert str(exc_info.value) == detail
    assert exc_info.value.detail == detail
    assert exc_info.value.status_code == status_code


def test_leaked_api_key_error_custom_status():
    """Test raising LeakedApiKeyError with custom status code."""
    detail = "Leaked API key detected"
    status_code = 400
    with pytest.raises(LeakedApiKeyError) as exc_info:
        raise LeakedApiKeyError(detail=detail, status_code=status_code)

    assert str(exc_info.value) == detail
    assert exc_info.value.detail == detail
    assert exc_info.value.status_code == status_code
