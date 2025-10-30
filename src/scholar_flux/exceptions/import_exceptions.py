## /exceptions/import_exceptions.py
"""The scholar_flux.exceptions.import_exceptions module implements exceptions for handling missing dependencies when
using the scholar_flux package. Although several packages are optional, attempting to use functionality that directly
depends on an uninstalled dependency should raise an error.

This package module produces the basic exceptions necessary to clearly identify when a dependency is missing.

"""
import logging

logger = logging.getLogger(__name__)


class OptionalDependencyImportError(Exception):
    """Base exception for Optional Dependency Issues."""

    def __init__(self, message="Optional Dependency not found"):
        """Initializes the foundational OptionalDependencyImportError that forms the basis of more specific error
        handling when dependencies are missing."""
        logger.error(message)
        super().__init__(message)


class ItsDangerousImportError(OptionalDependencyImportError):
    """Exception for itsdangerous Dependency Issues."""

    def __init__(self):
        """Initializes the `itsdangerous` import exception for improved logging before the exception is raised."""
        err = """Optional Dependency: itsdangerous backend is not installed.
        Please install the 'itsdangerous' package to use this feature."""
        super().__init__(message=err)


class CryptographyImportError(OptionalDependencyImportError):
    """Exception for cryptography Dependency Issues."""

    def __init__(self):
        """Initializes the `cryptography` import exception for improved logging before the exception is raised."""
        err = """Optional Dependency: cryptography backend is not installed.
        Please install the 'cryptography' package to use this feature."""
        super().__init__(message=err)


class RedisImportError(OptionalDependencyImportError):
    """Exception for missing redis backend."""

    def __init__(self):
        """Initializes the `redis` import exception for improved logging before the exception is raised."""
        err = """Optional Dependency: Redis backend is not installed.
        Please install the 'redis' package to use this feature."""
        super().__init__(message=err)


class SQLAlchemyImportError(OptionalDependencyImportError):
    """Exception for missing sql alchemy backend."""

    def __init__(self):
        """Initializes the `sqlalchemy` import exception for improved logging before the exception is raised."""
        err = """Optional Dependency: SQL Alchemy backend is not installed.
        Please install the 'sqlalchemy' package to use this feature."""
        super().__init__(message=err)


class MongoDBImportError(OptionalDependencyImportError):
    """Exception for Mongo Dependency Issues."""

    def __init__(self):
        """Initializes the `pymongo` import exception for improved logging before the exception is raised."""
        err = """Optional Dependency: MongoDB backend is not installed
        Please install the 'pymongo' package to use this feature."""
        super().__init__(message=err)


class XMLToDictImportError(OptionalDependencyImportError):
    """Exception for xmltodict Dependency Issues."""

    def __init__(self):
        """Initializes the `xmltodict` import exception for improved logging before the exception is raised."""
        err = """Optional Dependency: 'xmltodict' backend is not installed
        Please install the 'xmltodict' package to use this feature."""

        super().__init__(message=err)


class YAMLImportError(OptionalDependencyImportError):
    """Exception for yaml Dependency Issues."""

    def __init__(self):
        """Initializes the `yaml` import exception for improved logging before the exception is raised."""
        err = """Optional Dependency: 'yaml' backend is not installed
        Please install the 'yaml' package to use this feature."""

        super().__init__(message=err)


__all__ = [
    "OptionalDependencyImportError",
    "ItsDangerousImportError",
    "RedisImportError",
    "MongoDBImportError",
    "XMLToDictImportError",
    "SQLAlchemyImportError",
    "YAMLImportError",
    "CryptographyImportError",
]
