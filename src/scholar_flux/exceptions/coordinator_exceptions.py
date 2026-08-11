# /exceptions/coordinator_exceptions.py
"""Implements exceptions involving the creation of coordinators, the coordination of requests, response processing, and
caching."""


class CoordinatorException(Exception):
    """Base exception for Coordinator-related errors."""


class InvalidCoordinatorParameterException(CoordinatorException):
    """Coordinator exception raised when attempting to set an unintended injectable class dependency as an attribute of
    a Coordinator or parameter to a method."""


__all__ = ["CoordinatorException", "InvalidCoordinatorParameterException"]
