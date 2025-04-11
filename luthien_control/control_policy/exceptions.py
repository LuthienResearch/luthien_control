# Control Policy Exceptions


class ControlPolicyError(Exception):
    """Base exception for all control policy errors."""

    pass


class ApiKeyNotFoundError(ControlPolicyError):
    """Exception raised when the API key is not found in the settings."""

    pass


class NoRequestError(ControlPolicyError):
    """Exception raised when the request object is not found in the context."""

    pass


class ClientAuthenticationError(ControlPolicyError):
    """Exception raised when client API key authentication fails."""

    def __init__(self, detail: str, status_code: int = 401):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)


class ClientAuthenticationNotFoundError(ControlPolicyError):
    """Exception raised when the client API key is not found in the request."""

    def __init__(self, detail: str, status_code: int = 401):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)
