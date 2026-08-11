# /exceptions/util_exceptions.py
"""Implements exceptions for handling edge-cases when processing JSON files using custom path processing utilities."""


class LogDirectoryError(Exception):
    """Exception class raised for errors related to the creation of the package logging directory."""


class PackageInitializationError(Exception):
    """Exception raised when the ScholarFlux package cannot be initialized due to an unexpected error."""


class SessionCreationError(Exception):
    """Exception class raised for invalid operations in the creation of session objects."""


class SessionConfigurationError(SessionCreationError):
    """Exception class raised for invalid operations in configuration of session objects."""


class SessionInitializationError(SessionCreationError):
    """Exception class raised for invalid operations in the initialization of session objects."""


class CachedSessionValidationError(SessionInitializationError):
    """Exception class raised when the validation of a CachedSession instance fails."""


class SessionCacheDirectoryError(SessionCreationError):
    """Exception class raised for errors related to the creation of the package cache directory used by SessionCache."""


class SecretKeyError(ValueError):
    """Raised when the provided Fernet secret key is invalid."""


__all__ = [
    "LogDirectoryError",
    "PackageInitializationError",
    "SessionCreationError",
    "SessionConfigurationError",
    "SessionInitializationError",
    "CachedSessionValidationError",
    "SessionCacheDirectoryError",
    "SecretKeyError",
]
