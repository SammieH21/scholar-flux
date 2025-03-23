## /exceptions.storage_exceptions.py
import logging
logger = logging.getLogger(__name__)


class OptionalDependencyImportError(Exception):
    """Base exception for Optional Dependency Issues"""
    def __init__(self,message="Optional Dependency not found"):
        super().__init__(message)

class ItsDangerousImportError(OptionalDependencyImportError):
    """Base exception for Optional Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: itsdangerous backend is not installed.
        Please install the 'itsdangerous' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class RedisImportError(OptionalDependencyImportError):
    """Exception missing redis backend"""
    def __init__(self):
        err="""Optional Dependency: Redis backend is not installed.
        Please install the 'redis' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class SQLiteImportError(OptionalDependencyImportError):
    """Base exception for SQLLite Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: SQLite backend is not installed
        Please install the 'sqlite3' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class PostgresImportError(OptionalDependencyImportError):
    """Base exception for Redis Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: PostgreSQL backend is not installed
        Please install the 'psycopg2' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class MongoDBImportError(OptionalDependencyImportError):
    """Base exception for Redis Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: MongoDB backend is not installed
        Please install the 'pymongo' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class RequestsCacheImportError(OptionalDependencyImportError):
    """Base exception for Redis Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: 'Requests-Cache' backend is not installed
        Please install the 'requests-cache' package to use this feature."""

        logger.error(err)
        super().__init__(message=err)

