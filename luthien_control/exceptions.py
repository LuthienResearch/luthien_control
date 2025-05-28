class LuthienDBException(Exception):
    """Base exception for all Luthien DB related errors."""

    pass


class LuthienDBConfigurationError(LuthienDBException):
    """Exception raised when a database configuration is invalid or missing required variables."""

    pass


class LuthienDBConnectionError(LuthienDBException):
    """Exception raised when a connection to the database fails."""

    pass
