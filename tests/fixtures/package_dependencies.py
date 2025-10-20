import pytest
import importlib.util
import logging
from typing import Optional
from functools import lru_cache
from scholar_flux.data_storage import SQLAlchemyStorage, RedisStorage, MongoDBStorage

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def session_encryption_dependency() -> bool:
    """For determining whether to set up and test a cached session with encrypted storage."""
    return all(importlib.util.find_spec(pkg) for pkg in ["cryptography", "itsdangerous"])


@pytest.fixture(scope="session")
def xml_parsing_dependency() -> bool:
    """For determining whether xml can be implemented to parse xml responses into a json dictionary structure."""
    return all(importlib.util.find_spec(pkg) for pkg in ["xmltodict"])


@pytest.fixture(scope="session")
def yaml_parsing_dependency() -> bool:
    """For determining whether yaml can be implemented to parse yaml responses into a json dictionary structure."""
    return all(importlib.util.find_spec(pkg) for pkg in ["yaml"])


@pytest.fixture(scope="session")
def redis_dependency() -> bool:
    """Indicates whether the redis module is available."""
    return bool(importlib.util.find_spec("redis"))


@pytest.fixture(scope="session")
def mongodb_dependency() -> bool:
    """Indicates whether the pymongo module is available."""
    return bool(importlib.util.find_spec("pymongo"))


@pytest.fixture(scope="session")
def sqlalchemy_dependency() -> bool:
    """Indicates whether the sqlalchemy module is available."""
    return bool(importlib.util.find_spec("sqlalchemy"))


@lru_cache(maxsize=1)
def mongodb_available(host: str = "localhost", port: int = 27017) -> bool:
    """Helper function for determining whether MongoDB is available."""
    available = MongoDBStorage.is_available(host=host, port=port)
    if not available:
        logger.warning("Skipping tests for MongoDB")
    return available


@lru_cache(maxsize=1)
def sqlalchemy_available(url: Optional[str] = None) -> bool:
    """Helper function for determining whether SQL Alchemy is available."""
    available = SQLAlchemyStorage.is_available(url=url)
    if not available:
        logger.warning("Skipping tests for SQL Alchemy")
    return available


@lru_cache(maxsize=1)
def redis_available(host: str = "localhost", port: int = 6379) -> bool:
    """Helper function for determining whether the Redis Service is available."""
    available = RedisStorage.is_available(host=host, port=port)
    if not available:
        logger.warning("Skipping tests for Redis")
    return available


@pytest.fixture(scope="session")
def db_dependency_unavailable():
    """Provides a factory method for determining whether a db can be accessed."""

    def dependency_match(storage, **kwargs) -> bool:
        """Used to determine whether the requested storage is supported but unavailable."""
        match storage.lower():
            case "sql" | "sqlalchemy":
                return not sqlalchemy_available(**kwargs)
            case "mongo" | "mongodb" | "pymongo":
                return not mongodb_available(**kwargs)
            case "redis":
                return not redis_available(**kwargs)
            case _:
                # for all other dependencies, return False if not explicitly defined
                return False

    return dependency_match


__all__ = [
    "redis_dependency",
    "mongodb_dependency",
    "sqlalchemy_dependency",
    "redis_available",
    "mongodb_available",
    "sqlalchemy_available",
    "db_dependency_unavailable",
    "xml_parsing_dependency",
    "yaml_parsing_dependency",
    "session_encryption_dependency",
]
