# Control Policy Exceptions

from luthien_control.exceptions import LuthienException


class ControlPolicyError(LuthienException):
    """Base exception for all control policy errors.

    Attributes:
        policy_name (Optional[str]): The name of the policy where the error
            occurred, if specified.
        status_code (Optional[int]): An HTTP status code associated with this
            error, if specified.
        detail (Optional[str]): A detailed error message. If not provided directly
            during initialization but other arguments are, the first positional
            argument is used as the detail.
    """

    def __init__(
        self, *args, policy_name: str | None = None, status_code: int | None = None, detail: str | None = None
    ):
        """Initializes the ControlPolicyError.

        Args:
            *args: Arguments passed to the base Exception class.
            policy_name (Optional[str]): The name of the policy where the error occurred.
            status_code (Optional[int]): An HTTP status code associated with this error.
            detail (Optional[str]): A detailed error message. If not provided and `args`
                                    is not empty, the first argument in `args` is used.
        """
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
        """Initializes the PolicyLoadError.

        Args:
            *args: Arguments passed to the base Exception class.
            policy_name (Optional[str]): The name of the policy that failed to load.
            status_code (Optional[int]): An HTTP status code associated with this error.
            detail (Optional[str]): A detailed error message. If not provided and `args`
                                    is not empty, the first argument in `args` is used.
        """
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
        """Initializes the ClientAuthenticationError.

        Args:
            detail (str): A detailed error message explaining the authentication failure.
            status_code (int): The HTTP status code to associate with this error.
                               Defaults to 401 (Unauthorized).
        """
        # Pass detail positionally for Exception.__str__ and keywords for ControlPolicyError attributes
        super().__init__(detail, status_code=status_code, detail=detail)


class ClientAuthenticationNotFoundError(ControlPolicyError):
    """Exception raised when the client API key is not found in the request."""

    def __init__(self, detail: str, status_code: int = 401):
        """Initializes the ClientAuthenticationNotFoundError.

        Args:
            detail (str): A detailed error message explaining why the key was not found.
            status_code (int): The HTTP status code to associate with this error.
                               Defaults to 401 (Unauthorized).
        """
        # Pass detail positionally for Exception.__str__ and keywords for ControlPolicyError attributes
        super().__init__(detail, status_code=status_code, detail=detail)


class LeakedApiKeyError(ControlPolicyError):
    """Exception raised when a leaked API key is detected."""

    def __init__(self, detail: str, status_code: int = 403):
        """Initializes the LeakedApiKeyError.

        Args:
            detail (str): A detailed error message explaining the leaked key detection.
            status_code (int): The HTTP status code to associate with this error.
                               Defaults to 403 (Forbidden).
        """
        # Pass detail positionally for Exception.__str__ and keywords for ControlPolicyError attributes
        super().__init__(detail, status_code=status_code, detail=detail)
