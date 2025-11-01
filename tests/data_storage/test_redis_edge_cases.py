import pytest
from unittest.mock import patch
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.exceptions import (
    RedisImportError,
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
)
from tests.testing_utilities import raise_error


@pytest.fixture(scope="session", autouse=True)
def skip_missing_redis_dependency(db_dependency_unavailable):
    """Helper fixture for only performing tests for redis when the client and dependency are available."""
    if db_dependency_unavailable("redis"):
        pytest.skip()


def test_redis_retrieval_error(redis_test_storage, monkeypatch, caplog):
    """Tests single-record retrieval edge cases with redis."""
    from redis import RedisError

    e = "Directly raised exception"
    key = "non-existent-key"
    msg = f"Error during attempted retrieval of key {key} (namespace = '{redis_test_storage.namespace}'): {e}"
    monkeypatch.setattr(redis_test_storage.client, "get", raise_error(RedisError, e))

    retrieved = redis_test_storage.retrieve(key)

    assert retrieved is None
    assert msg in caplog.text

    with redis_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
        retrieved = redis_test_storage.retrieve(key)
    assert msg in str(excinfo.value)


def test_redis_retrieve_all_error(redis_test_storage, monkeypatch, caplog):
    """Tests complete-record retrieval edge cases with redis."""
    from redis import RedisError

    e = "Directly raised exception"
    msg = "Error during attempted retrieval of records from namespace"
    monkeypatch.setattr(redis_test_storage, "retrieve_keys", raise_error(RedisError, e))
    all_retrieved = redis_test_storage.retrieve_all()
    assert not all_retrieved
    assert msg in caplog.text

    with redis_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
        _ = redis_test_storage.retrieve_all()
    assert msg in str(excinfo.value)


def test_retrieve_keys_redis_error(redis_test_storage, monkeypatch, caplog):
    """Tests multi-key retrieval edge cases with redis."""
    from redis import RedisError

    e = "Directly raised exception"
    msg = f"Error during attempted retrieval of all keys from namespace '{redis_test_storage.namespace}"
    monkeypatch.setattr(redis_test_storage.client, "scan_iter", raise_error(RedisError, e))

    all_retrieved_keys = redis_test_storage.retrieve_keys()
    assert not all_retrieved_keys
    assert msg in caplog.text

    with redis_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
        _ = redis_test_storage.retrieve_keys()
    assert msg in str(excinfo.value)


def test_redis_update_error(redis_test_storage, monkeypatch, caplog):
    """Tests update edge cases in redis."""
    from redis import RedisError

    e = "Directly raised exception"
    key = "non-existent-key"
    value = {"data": 1}
    msg = f"Error during attempted update of key {key} (namespace = '{redis_test_storage.namespace}': {e}"
    monkeypatch.setattr(redis_test_storage.client, "set", raise_error(RedisError, e))
    redis_test_storage.update(key, value)
    assert msg in caplog.text

    with redis_test_storage.with_raise_on_error(), pytest.raises(CacheUpdateException) as excinfo:
        _ = redis_test_storage.update(key, value)
    assert msg in str(excinfo.value)


def test_redis_delete_error(redis_test_storage, monkeypatch, caplog):
    """Tests single-record deletion edge cases with  redis."""
    from redis import RedisError

    e = "Directly raised exception"
    key = "non-existent-key"
    msg = f"Error during attempted deletion of key {key} (namespace = '{redis_test_storage.namespace}'): {e}"
    monkeypatch.setattr(redis_test_storage, "verify_cache", raise_error(RedisError, e))
    redis_test_storage.delete(key)
    assert msg in caplog.text

    with redis_test_storage.with_raise_on_error(), pytest.raises(CacheDeletionException) as excinfo:
        _ = redis_test_storage.delete(key)
    assert msg in str(excinfo.value)


def test_redis_delete_all_error(redis_test_storage, monkeypatch, caplog):
    """Tests full-record deletion edge cases with in redis."""
    from redis import RedisError

    e = "Directly raised exception"
    msg = f"Error during attempted deletion of all records from namespace '{redis_test_storage.namespace}': {e}"
    monkeypatch.setattr(redis_test_storage.client, "scan_iter", raise_error(RedisError, e))
    redis_test_storage.delete_all()
    assert msg in caplog.text

    with redis_test_storage.with_raise_on_error(), pytest.raises(CacheDeletionException) as excinfo:
        _ = redis_test_storage.delete_all()
    assert msg in str(excinfo.value)


def test_redis_verify_cache_error(redis_test_storage, monkeypatch, caplog):
    """Tests cache verification edge cases in redis."""
    from redis import RedisError

    intkey = 271

    with pytest.raises(ValueError) as excinfo:
        _ = redis_test_storage.verify_cache(intkey)
    assert f"Key invalid. Received {intkey} (namespace = '{redis_test_storage.namespace}')" in str(excinfo.value)

    e = "Directly raised exception"
    key = "non-existent-key"
    msg = f"Error during the verification of the existence of key {key} (namespace = '{redis_test_storage.namespace}'): {e}"
    monkeypatch.setattr(redis_test_storage.client, "exists", raise_error(RedisError, e))
    redis_test_storage.verify_cache(key)
    assert msg in caplog.text

    with redis_test_storage.with_raise_on_error(), pytest.raises(CacheVerificationException) as excinfo_two:
        _ = redis_test_storage.verify_cache(key)
    assert msg in str(excinfo_two.value)


def test_redis_unavailable(redis_test_storage, caplog):
    """Verifies that, when the redis package is not installed, an error will be raised."""
    with patch("scholar_flux.data_storage.redis_storage.redis", None):
        assert not redis_test_storage.is_available()
        assert "The redis module is not available" in caplog.text

        with pytest.raises(RedisImportError) as excinfo:
            RedisStorage()
        assert "Optional Dependency: Redis backend is not installed" in str(excinfo.value)
        assert "Please install the 'redis' package to use this feature." in str(excinfo.value)


def test_redis_server_unavailable(redis_test_storage, monkeypatch, caplog):
    """Verifies that the behavior of the RedisStorage is as expected when attempting to create a connection."""
    import redis
    from redis import ConnectionError

    msg = "Won't connect"
    host, port = RedisStorage.DEFAULT_CONFIG["host"], RedisStorage.DEFAULT_CONFIG["port"]

    monkeypatch.setattr(redis, "Redis", raise_error(ConnectionError, msg))

    assert not redis_test_storage.is_available()

    assert f"An active Redis service could not be found at {host}:{port}: {msg}" in caplog.text


def test_missing_namespace(redis_test_storage, monkeypatch, caplog):
    """Tests whether delete_all will successfully retain data as intended.

    This method uses a patch that should raise an error deletion is attempted nonetheless

    """

    current_namespace = redis_test_storage.namespace
    default_namespace = RedisStorage.DEFAULT_NAMESPACE
    try:
        redis_test_storage.namespace = None
        RedisStorage.DEFAULT_NAMESPACE = None  # type: ignore
        monkeypatch.setattr(redis_test_storage.client, "scan_iter", raise_error(ValueError))
        redis_test_storage.delete_all()
        assert (
            "For safety purposes, the RedisStorage will not delete any records in the absence "
            "of a namespace. Skipping..."
        ) in caplog.text

        with pytest.raises(KeyError) as excinfo:
            _ = RedisStorage(namespace=23)  # type: ignore
        msg = f"A non-empty namespace string must be provided for the RedisStorage. Received {type(23)}"

        assert msg in caplog.text
        assert msg in str(excinfo.value)

        caplog.clear()
        with pytest.raises(KeyError) as excinfo:
            _ = RedisStorage(namespace="")  # type: ignore
        msg = f"A non-empty namespace string must be provided for the RedisStorage. Received {type('')}"

        assert msg in caplog.text
        assert msg in str(excinfo.value)

    finally:
        redis_test_storage.namespace = current_namespace
        RedisStorage.DEFAULT_NAMESPACE = default_namespace
