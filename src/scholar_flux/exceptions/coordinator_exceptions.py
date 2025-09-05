# api_exceptions.py


class CoordinatorException(Exception):
    """Base exception for Coordinator-related errors."""

    pass


class InvalidCoordinatorParameterException(CoordinatorException):
    """
    Coordinator exception raised when attempting to set an unintended injectable
    class dependency as an attribute of a Coordinator
    """

    pass
