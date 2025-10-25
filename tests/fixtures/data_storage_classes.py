import pytest

from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.data_storage.mongodb_storage import MongoDBStorage
from scholar_flux.data_storage.sql_storage import SQLAlchemyStorage
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage.null_storage import NullStorage
from pathlib import Path


@pytest.fixture(scope="module")
def redis_test_config():
    """Redis configuration for testing."""
    return {
        "host": RedisStorage.DEFAULT_CONFIG["host"],
        "port": RedisStorage.DEFAULT_CONFIG["port"],
        "db": 0,
    }


@pytest.fixture(scope="module")
def storage_test_namespace():
    """Indicates the specific storage namespace to use for testing when creating data storage caches."""
    return "cache_collection"


@pytest.fixture(scope="module")
def mongo_test_config():
    """MongoDB configuration for testing."""
    return {
        "host": MongoDBStorage.DEFAULT_CONFIG["host"],
        "port": MongoDBStorage.DEFAULT_CONFIG["port"],
        "database": "sf_data_storage_tests",
        "collection": "cache_collection",
    }


@pytest.fixture(scope="module")
def sqlite_test_config():
    """SQL configuration for testing."""
    return {
        "url": "sqlite:///" + str(Path(__file__).resolve().parent.parent / "mocks/sql_data_storage_test.sqlite"),
        "echo": False,
    }


@pytest.fixture(scope="module")
def redis_test_storage(redis_test_config, storage_test_namespace):
    """Create a Redis Data Storage instance to use for later testing at the module level."""
    return RedisStorage(namespace=storage_test_namespace, **redis_test_config)


@pytest.fixture(scope="module")
def mongo_test_storage(mongo_test_config):
    """Create a MongoDB Data Storage instance to use for later testing at the module level."""
    return MongoDBStorage(**mongo_test_config)


@pytest.fixture(scope="module")
def mongo_nm_test_storage(mongo_test_config, storage_test_namespace):
    """Create a MongoDB Data Storage instance to use for later testing at the module level.

    This storage instance uses a separate namespace than the original `mongo_test_storage` to validate namespace
    filtering for MongoDB.

    """
    return MongoDBStorage(namespace=storage_test_namespace, **mongo_test_config)


@pytest.fixture(scope="module")
def sqlite_test_storage(sqlite_test_config):
    """Create a SQL Data Storage instance to use for later testing at the module level."""
    return SQLAlchemyStorage(**sqlite_test_config)


@pytest.fixture(scope="module")
def sqlite_nm_test_storage(sqlite_test_config, storage_test_namespace):
    """Create a SQL Data Storage instance.

    This storage instance uses a separate namespace than the original `sqlite_test_storage` to validate namespace
    filtering for SQLite.

    """
    return SQLAlchemyStorage(namespace=storage_test_namespace, **sqlite_test_config)


@pytest.fixture(scope="module")
def in_memory_test_storage():
    """Create an In Memory Data Storage instance."""
    return InMemoryStorage()


@pytest.fixture(scope="module")
def in_memory_nm_test_storage(storage_test_namespace):
    """Create an in-memory Data Storage instance.

    This storage instance uses a separate namespace than the original `in_memory_test_storage` to validate namespace
    filtering for in- memory caching.

    """
    return InMemoryStorage(namespace=storage_test_namespace)


@pytest.fixture(scope="module")
def null_test_storage():
    """Creates a Null Data Storage instance that essentially prevents the caching of response processing data."""
    return NullStorage()


__all__ = [
    "redis_test_config",
    "storage_test_namespace",
    "mongo_test_config",
    "sqlite_test_config",
    "redis_test_storage",
    "mongo_test_storage",
    "mongo_nm_test_storage",
    "sqlite_test_storage",
    "sqlite_nm_test_storage",
    "in_memory_test_storage",
    "in_memory_nm_test_storage",
    "null_test_storage",
]
