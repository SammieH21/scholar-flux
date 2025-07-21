## import_exceptions.py
import logging
logger = logging.getLogger(__name__)


class OptionalDependencyImportError(Exception):
    """Base exception for Optional Dependency Issues"""
    def __init__(self,message="Optional Dependency not found"):
        super().__init__(message)

class ItsDangerousImportError(OptionalDependencyImportError):
    """Exception for itsdangerous Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: itsdangerous backend is not installed.
        Please install the 'itsdangerous' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class CryptographyImportError(OptionalDependencyImportError):
    """Exception for cryptography Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: cryptography backend is not installed.
        Please install the 'cryptography' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)


class RedisImportError(OptionalDependencyImportError):
    """Exception for missing redis backend"""
    def __init__(self):
        err="""Optional Dependency: Redis backend is not installed.
        Please install the 'redis' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class SQLAlchemyImportError(OptionalDependencyImportError):
    """Exception for missing sql alchemy backend"""
    def __init__(self):
        err="""Optional Dependency: Sql Alchemy backend is not installed.
        Please install the 'sqlalchemy' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class SQLiteImportError(OptionalDependencyImportError):
    """Exception for SQLite Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: SQLite backend is not installed
        Please install the 'sqlite3' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class PostgresImportError(OptionalDependencyImportError):
    """Exception for Postgres Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: PostgreSQL backend is not installed
        Please install the 'psycopg2' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class MongoDBImportError(OptionalDependencyImportError):
    """Exception for Mongo Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: MongoDB backend is not installed
        Please install the 'pymongo' package to use this feature."""
        logger.error(err)
        super().__init__(message=err)

class RequestsCacheImportError(OptionalDependencyImportError):
    """Exception for requests-cache Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: 'Requests-Cache' backend is not installed
        Please install the 'requests-cache' package to use this feature."""

        logger.error(err)
        super().__init__(message=err)

class XMLToDictImportError(OptionalDependencyImportError):
    """Exception for xmltodict Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: 'xmltodict' backend is not installed
        Please install the 'xmltodict' package to use this feature."""

        logger.error(err)
        super().__init__(message=err)

class YAMLImportError(OptionalDependencyImportError):
    """Exception for yaml Dependency Issues"""
    def __init__(self):
        err="""Optional Dependency: 'yaml' backend is not installed
        Please install the 'yaml' package to use this feature."""

        logger.error(err)
        super().__init__(message=err)
