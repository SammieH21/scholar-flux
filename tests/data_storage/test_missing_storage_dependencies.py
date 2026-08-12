import importlib
from unittest.mock import patch

import pytest

import scholar_flux.data_storage.mongodb_storage
import scholar_flux.data_storage.redis_storage
import scholar_flux.data_storage.sql_storage
from scholar_flux.data_storage import MongoDBStorage, RedisStorage, SQLAlchemyStorage


def test_sql_missing(sqlalchemy_dependency):
    """Verifies the behavior of the sql_storage module when sql is missing."""
    try:
        with patch.dict("sys.modules", {"sqlalchemy": None}):
            importlib.reload(scholar_flux.data_storage.sql_storage)
            from scholar_flux.data_storage.sql_storage import (
                JSON,
                Column,
                DeclarativeBase,
                Integer,
                SQLAlchemyImportError,
                String,
                create_engine,
                exc,
                sessionmaker,
                sqlalchemy,
            )

            Column()  # no-op placeholder
            assert DeclarativeBase is object
            assert scholar_flux.data_storage.sql_storage.sqlalchemy is None
            assert create_engine is None
            assert String is Integer is JSON is exc is None
            assert sessionmaker is None
            assert sqlalchemy is None

            with pytest.raises(SQLAlchemyImportError):
                SQLAlchemyStorage()
    finally:
        importlib.reload(scholar_flux.data_storage.sql_storage)


def test_mongo_missing(mongodb_dependency):
    """Verifies the behavior of the mongo_storage module when mongo is missing."""
    try:
        with patch.dict("sys.modules", {"pymongo": None}):
            importlib.reload(scholar_flux.data_storage.mongodb_storage)
            from scholar_flux.data_storage.mongodb_storage import (
                ConnectionFailure,
                DuplicateKeyError,
                MongoClient,
                MongoDBImportError,
                PyMongoError,
                ServerSelectionTimeoutError,
            )

            assert scholar_flux.data_storage.mongodb_storage.pymongo is None
            assert MongoClient is None
            assert ServerSelectionTimeoutError is Exception
            assert ConnectionFailure is Exception
            assert DuplicateKeyError is Exception
            assert PyMongoError is Exception

            with pytest.raises(MongoDBImportError):
                MongoDBStorage()
    finally:
        importlib.reload(scholar_flux.data_storage.mongodb_storage)


def test_redis_missing(redis_dependency):
    """Verifies the behavior of the redis_storage module when redis is missing."""
    try:
        with patch.dict("sys.modules", {"redis": None}):
            importlib.reload(scholar_flux.data_storage.redis_storage)
            from scholar_flux.data_storage.redis_storage import (
                ConnectionError,
                RedisError,
                RedisImportError,
                TimeoutError,
            )

            assert scholar_flux.data_storage.redis_storage.redis is None
            assert ConnectionError is Exception
            assert RedisError is Exception
            assert TimeoutError is Exception

            with pytest.raises(RedisImportError):
                RedisStorage()
    finally:
        importlib.reload(scholar_flux.data_storage.redis_storage)
