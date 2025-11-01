import pytest
from unittest.mock import patch
import re
from scholar_flux.data_storage.mongodb_storage import (
    MongoDBStorage,
    MongoDBImportError,
    PyMongoError,
    ConnectionFailure,
)
from scholar_flux.exceptions import (
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
)
from tests.testing_utilities import raise_error


@pytest.fixture(scope="session", autouse=True)
def skip_missing_mongo_dependency(db_dependency_unavailable):
    """Helper fixture for performing tests for mongo only when the client and dependency are available."""
    if db_dependency_unavailable("mongo"):
        pytest.skip()


def test_mongo_retrieval_failure(mongo_test_storage, monkeypatch, caplog):
    """Tests single-record retrieval edge cases with MongoDB."""
    from pymongo.errors import PyMongoError

    e = "DB error"
    key = "non-existent-key"
    msg = f"Error during attempted retrieval of key {key} (namespace = '{mongo_test_storage.namespace}'): {e}"
    monkeypatch.setattr(mongo_test_storage.collection, "find_one", raise_error(PyMongoError, e))

    retrieved = mongo_test_storage.retrieve(key)
    assert retrieved is None

    assert msg in caplog.text

    with mongo_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
        retrieved = mongo_test_storage.retrieve(key)
    assert msg in str(excinfo.value)


def test_mongo_retrieve_all_error(mongo_test_storage, monkeypatch, caplog):
    """Tests multi-record retrieval edge cases with Mongodb."""
    e = "DB error"
    msg = "Error during attempted retrieval of records from namespace"
    monkeypatch.setattr(mongo_test_storage.collection, "find", raise_error(PyMongoError, e))
    result = mongo_test_storage.retrieve_all()
    assert result == {}
    assert msg in caplog.text

    with mongo_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
        _ = mongo_test_storage.retrieve_all()
    assert msg in str(excinfo.value)


def test_mongo_retrieve_keys_error(mongo_test_storage, monkeypatch, caplog):
    """Tests multi-key retrieval edge cases with MongoDB."""
    e = "DB error"
    msg = f"Error during attempted retrieval of all keys from namespace '{mongo_test_storage.namespace}"
    monkeypatch.setattr(mongo_test_storage.collection, "distinct", raise_error(PyMongoError, e))
    keys = mongo_test_storage.retrieve_keys()
    assert keys == []
    assert msg in caplog.text

    with mongo_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
        _ = mongo_test_storage.retrieve_keys()
    assert msg in str(excinfo.value)


def test_mongo_update_error(mongo_test_storage, caplog):
    """Tests update edge cases in MongoDB."""
    e = "DB error"
    key = "some_key"
    value = {"data": 1}
    msg = f"Error during attempted update of key {key} (namespace = '{mongo_test_storage.namespace}': {e}"
    with patch.object(mongo_test_storage, "collection") as mock_collection:
        mock_collection.update_one.side_effect = PyMongoError(e)
        # Patch verify_cache to False so update_one is called
        with patch.object(mongo_test_storage, "verify_cache", return_value=False):
            mongo_test_storage.update(key, value)
            assert msg in caplog.text

            with mongo_test_storage.with_raise_on_error(), pytest.raises(CacheUpdateException) as excinfo:
                mongo_test_storage.update(key, value)
            assert msg in str(excinfo.value)


def test_mongo_delete_error(mongo_test_storage, caplog):
    """Tests single-record deletion edge cases with in MongoDB."""
    e = "DB error"
    key = "some_key"
    msg = f"Error during attempted deletion of key {key} (namespace = '{mongo_test_storage.namespace}'): {e}"

    mongo_test_storage.delete(key)
    assert f"Record for key {key} (namespace = '{mongo_test_storage.namespace}') does not exist"

    with patch.object(mongo_test_storage, "collection") as mock_collection:
        mock_collection.delete_one.side_effect = PyMongoError(e)
        mongo_test_storage.delete(key)
        assert msg in caplog.text

        with mongo_test_storage.with_raise_on_error(), pytest.raises(CacheDeletionException) as excinfo:
            mongo_test_storage.delete(key)
        assert msg in str(excinfo.value)


def test_mongo_delete_all_error(mongo_test_storage, caplog):
    """Tests full-record deletion edge cases with in MongoDB."""
    e = "DB error"
    msg = f"Error during attempted deletion of all records from namespace '{mongo_test_storage.namespace}': {e}"
    with patch.object(mongo_test_storage, "collection") as mock_collection:
        mock_collection.delete_many.side_effect = PyMongoError(e)
        mongo_test_storage.delete_all()
        assert msg in caplog.text

        with mongo_test_storage.with_raise_on_error(), pytest.raises(CacheDeletionException) as excinfo:
            mongo_test_storage.delete_all()
        assert msg in str(excinfo.value)


def test_mongo_verify_cache_error(mongo_test_storage, monkeypatch, caplog):
    """Tests cache verification edge cases in MongoDB."""
    e = "DB error"
    key = "some_key"
    msg = (
        re.escape(
            f"Error during the verification of the existence of key {key} (namespace = '{mongo_test_storage.namespace}'):"
        )
        + f".*{e}"
    )
    monkeypatch.setattr(mongo_test_storage.collection, "find_one", raise_error(PyMongoError, e))
    result = mongo_test_storage.verify_cache(key)
    assert result is False
    assert re.search(msg, caplog.text) is not None

    with mongo_test_storage.with_raise_on_error(), pytest.raises(CacheVerificationException) as excinfo:
        _ = mongo_test_storage.verify_cache(key)
    assert re.search(msg, str(excinfo.value)) is not None


def test_mongo_unavailable(mongo_test_storage, caplog):
    """Verifies that, when the mongo package is not installed, an error will be raised."""
    with patch("scholar_flux.data_storage.mongodb_storage.pymongo", None):
        assert not mongo_test_storage.is_available()
        assert "The pymongo module is not available" in caplog.text

        with pytest.raises(MongoDBImportError) as excinfo:
            MongoDBStorage()
        assert "Optional Dependency: MongoDB backend is not installed" in str(excinfo.value)
        assert "Please install the 'pymongo' package to use this feature." in str(excinfo.value)


def test_mongo_server_unavailable(mongo_test_storage, caplog):
    """Verifies that the behavior of the MongoDBStorage is as expected when attempting to create a connection."""

    e = "Won't connect"

    with patch("scholar_flux.data_storage.mongodb_storage.MongoClient", raise_error(ConnectionFailure, e)):
        assert not mongo_test_storage.is_available()
