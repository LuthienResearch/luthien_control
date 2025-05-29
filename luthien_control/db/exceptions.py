"""Database-specific exceptions for the Luthien Control project."""

from sqlalchemy.exc import IntegrityError

from luthien_control.exceptions import LuthienDBException


class LuthienDBOperationError(LuthienDBException):
    """Base exception for database operation errors.

    This exception is raised when a database operation fails for any reason.
    It serves as a base class for more specific database operation errors.
    """

    pass


class LuthienDBQueryError(LuthienDBOperationError):
    """Exception raised when a database query fails.

    This exception is raised when a SELECT query fails to execute properly.
    """

    pass


class LuthienDBTransactionError(LuthienDBOperationError):
    """Exception raised when a database transaction fails.

    This exception is raised when a transaction (commit, rollback) fails.
    """

    pass


class LuthienDBIntegrityError(LuthienDBOperationError):
    """Exception raised when a database integrity constraint is violated.

    This exception wraps SQLAlchemy's IntegrityError and provides a more
    specific error type for the Luthien Control project.
    """

    def __init__(self, message: str, original_error: IntegrityError = None):
        """Initialize the exception.

        Args:
            message: A descriptive error message
            original_error: The original IntegrityError that was raised
        """
        super().__init__(message)
        self.original_error = original_error
