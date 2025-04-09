class ApiKeyNotFoundError(Exception):
    """Exception raised when the API key is not found in the settings."""

    pass


class NoRequestError(Exception):
    """Exception raised when the request is not found in the context."""

    pass
