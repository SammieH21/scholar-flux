# /exceptions/path_exceptions.py
"""Implements exceptions for handling edge-cases when processing JSON files using custom path processing utilities."""


class LogDirectoryError(Exception):
    """Exception class raised for errors related to the creation of the package logging directory."""

    pass


class PackageInitializationError(Exception):
    """Exception raised when the ScholarFlux package cannot be initialized due to an unexpected error."""

    pass


class SessionCreationError(Exception):
    """Exception class raised for invalid operations in the creation of session objects."""

    pass


class SessionConfigurationError(SessionCreationError):
    """Exception class raised for invalid operations in configuration of session objects."""

    pass


class SessionInitializationError(SessionCreationError):
    """Exception class raised for invalid operations in the initialization of session objects."""

    pass


class SessionCacheDirectoryError(SessionCreationError):
    """Exception class raised for errors related to the creation of the package cache directory used by SessionCache."""

    pass


class SecretKeyError(ValueError):
    """Raised when the provided Fernet secret key is invalid."""

    pass


__all__ = [
    "LogDirectoryError",
    "PackageInitializationError",
    "SessionCreationError",
    "SessionConfigurationError",
    "SessionInitializationError",
    "SessionCacheDirectoryError",
    "SecretKeyError",
]
