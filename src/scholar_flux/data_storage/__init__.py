# /data_storage
"""The scholar_flux.data_storage module contains the core storage definitions used to cache the response content,
records and metadata for each unique page/batch of records under a key used for cache identification.

Core components:
    - DataCacheManager: Contains the higher level methods used to create and interact with the processing cache storage
                        methods in a predictable manner.
    - SQLAlchemyStorage: Contains the core methods needed to interact with a range of SQL Databases (and duckdb) using
                         the same underlying interface. By default, this class uses sqlalchemy to set up a db in a
                         consistent location.
    - RedisStorage: Contains the core methods to the Redis Client. This storage defaults to localhost, port 6379
    - MongoStorage: Contains the core methods used to interact with the Mongo DB database. By default, this class
                    attempts to Mongo DB on localhost on port 27017.
    - InMemoryStorage: The default storage method - simply saves processed request content and responses to a
                       temporary dictionary that is deleted when the python session is stopped
    - NullStorage: A No-Op storage method that is used to effectively turn off the use of storage.
                   This module is included for compatibility with the static typing used throughout the package

In addition, Exceptions for missing dependencies are set to return storage-specific errors if a storage
is initialized without the necessary dependencies:

    SQLAlchemyStorage -> sqlalchemy
    MongoStorage -> pymongo
    RedisStorage -> redis
    SQLAlchemyStorage -> sqlalchemy

Example use:
    >>> from scholar_flux import DataCacheManager, SearchCoordinator
    >>> processing_cache = DataCacheManager.with_storage('redis')
    >>> SearchCoordinator(query = 'Programming', cache_manager = processing_cache)

"""
from scholar_flux.exceptions import (
    OptionalDependencyImportError,
    RedisImportError,
    MongoDBImportError,
    SQLAlchemyImportError,
)


from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.data_storage.data_cache_manager import DataCacheManager
from scholar_flux.data_storage.sql_storage import SQLAlchemyStorage
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.data_storage.mongodb_storage import MongoDBStorage
from scholar_flux.data_storage.null_storage import NullStorage

__all__ = [
    "OptionalDependencyImportError",
    "RedisImportError",
    "MongoDBImportError",
    "SQLAlchemyImportError",
    "DataCacheManager",
    "ABCStorage",
    "SQLAlchemyStorage",
    "InMemoryStorage",
    "RedisStorage",
    "MongoDBStorage",
    "NullStorage",
]
