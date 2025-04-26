# Control Policy Exceptions


class ControlPolicyError(Exception):
    """Base exception for all control policy errors."""

    def __init__(
        self, *args, policy_name: str | None = None, status_code: int | None = None, detail: str | None = None
    ):
        super().__init__(*args)
        self.policy_name = policy_name
        self.status_code = status_code
        # Use the first arg as detail if detail kwarg is not provided and args exist
        self.detail = detail or (args[0] if args else None)


class PolicyLoadError(ValueError, ControlPolicyError):
    """Custom exception for errors during policy loading/instantiation."""

    # Inherit from ValueError for semantic meaning (bad value/config)
    # Inherit from ControlPolicyError for categorization
    def __init__(
        self, *args, policy_name: str | None = None, status_code: int | None = None, detail: str | None = None
    ):
        # Explicitly call ControlPolicyError.__init__ to handle kwargs
        ControlPolicyError.__init__(self, *args, policy_name=policy_name, status_code=status_code, detail=detail)
        # We might still want to call ValueError's init if it does something useful,
        # but for now, prioritizing ControlPolicyError's handling seems correct.
        # super(ValueError, self).__init__(*args) # Potentially add if needed


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
        self.status_code = status_code  # Keep this for clarity if needed, but super() sets it
        # Pass status_code and detail to the base class initializer
        super().__init__(detail, status_code=status_code, detail=detail)


class ClientAuthenticationNotFoundError(ControlPolicyError):
    """Exception raised when the client API key is not found in the request."""

    def __init__(self, detail: str, status_code: int = 401):
        self.detail = detail
        self.status_code = status_code  # Keep this for clarity if needed, but super() sets it
        # Pass status_code and detail to the base class initializer
        super().__init__(detail, status_code=status_code, detail=detail)
