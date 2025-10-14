import pytest
from unittest.mock import patch
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.exceptions import RedisImportError

@pytest.fixture(autouse=True)
def redis_is_available(db_dependency_unavailable):
    """Helper fixture for only performing tests for redis when the client and dependency are available"""
    
    if db_dependency_unavailable('redis'):
        pytest.skip()


def test_redis_retrieval_failure(redis_test_storage, monkeypatch, caplog):
    """Helper method to test retrieval edge cases with data retrieval in redis"""
    from redis import RedisError

    e = "Directly raised exception"
    key = 'non-existent-key'
    monkeypatch.setattr(redis_test_storage.client, "get", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError(e)))

    retrieved = redis_test_storage.retrieve(key)

    assert retrieved is None
    assert f"Error during attempted retrieval of key {key} (namespace = '{redis_test_storage.namespace}'): {e}" in caplog.text

    monkeypatch.setattr(redis_test_storage.client, "scan_iter", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError(e)))

    all_retrieved_keys = redis_test_storage.retrieve_keys()
    assert not all_retrieved_keys
    assert f"Error during attempted retrieval of all keys from namespace '{redis_test_storage.namespace}" in caplog.text

    caplog.clear()
    monkeypatch.setattr(redis_test_storage, "retrieve_keys", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError(e)))
    all_retrieved = redis_test_storage.retrieve_all()
    assert not all_retrieved
    assert "Error during attempted retrieval of records from namespace" in caplog.text

def test_redis_update_failure(redis_test_storage, monkeypatch, caplog):
    """Helper method to test update edge cases with data retrieval in redis"""
    from redis import RedisError

    e = "Directly raised exception"
    key = 'non-existent-key'
    monkeypatch.setattr(redis_test_storage.client, "set", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError(e)))
    redis_test_storage.update('non-existent-key', {'data': 1})
    assert f"Error during attempted update of key {key} (namespace = '{redis_test_storage.namespace}': {e}" in caplog.text

def test_redis_delete_failure(redis_test_storage, monkeypatch, caplog):
    """Helper method to test deletion edge cases with data retrieval in redis"""
    from redis import RedisError

    e = "Directly raised exception"
    key = 'non-existent-key'
    monkeypatch.setattr(redis_test_storage, "verify_cache", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError(e)))
    redis_test_storage.delete('non-existent-key')
    assert (f"Error during attempted deletion of key {key}") in caplog.text
    assert f"Error during attempted deletion of key {key} (namespace = '{redis_test_storage.namespace}'): {e}" in caplog.text

    monkeypatch.setattr(redis_test_storage.client, "scan_iter", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError(e)))
    redis_test_storage.delete_all()
    assert f"Error during attempted deletion of all keys from namespace '{redis_test_storage.namespace}': {e}" in caplog.text

def test_redis_verify_cache_failure(redis_test_storage, monkeypatch, caplog):
    """Helper method to test cache verification edge cases with data retrieval in redis"""
    from redis import RedisError

    intkey=271
    with pytest.raises(ValueError) as excinfo:
        _ = redis_test_storage.verify_cache(intkey)
    assert f"Key invalid. Received {intkey} (namespace = '{redis_test_storage.namespace}')" in str(excinfo.value)

    e = "Directly raised exception"
    key = 'non-existent-key'
    monkeypatch.setattr(redis_test_storage.client, "exists", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError(e)))
    redis_test_storage.verify_cache(key)
    assert f"Error during the verification of the existence of key {key} (namespace = '{redis_test_storage.namespace}'): {e}" in caplog.text

def test_redis_unavailable(redis_test_storage, caplog):
    """Validates that, when the redis package is not installed, an error will be raised"""
    with patch("scholar_flux.data_storage.redis_storage.redis", None):
        assert not redis_test_storage.is_available()
        assert "The redis module is not available" in caplog.text

        with pytest.raises(RedisImportError) as excinfo:
            RedisStorage()
        assert "Optional Dependency: Redis backend is not installed" in str(excinfo.value)
        assert "Please install the 'redis' package to use this feature." in str(excinfo.value)


def test_redis_server_unavailable(redis_test_storage, monkeypatch, caplog):
    """Verifies that the behavior of the RedisStorage is as expected when attempting to create a preliminary connection"""
    import redis
    from redis import ConnectionError

    msg = "Won't connect"
    host, port = RedisStorage.DEFAULT_REDIS_CONFIG['host'], RedisStorage.DEFAULT_REDIS_CONFIG['port']

    monkeypatch.setattr(redis, "Redis", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError(msg)))

    assert not redis_test_storage.is_available()

    assert f"An active Redis service could not be found at {host}:{port}: {msg}" in caplog.text


def test_missing_namespace(redis_test_storage, monkeypatch, caplog):
    """
    Tests whether delete_all will successfully retain data as intended. this method uses a patch that should raise
    an error deletion is attempted nonetheless
    """

    current_namespace = redis_test_storage.namespace
    default_namespace = RedisStorage.DEFAULT_NAMESPACE
    try:
        redis_test_storage.namespace = None
        RedisStorage.DEFAULT_NAMESPACE = None # type: ignore
        monkeypatch.setattr(redis_test_storage.client, "scan_iter", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError()))
        redis_test_storage.delete_all()
        assert ("For safety purposes, the RedisStorage will not delete any records in the absence "
                "of a namespace. Skipping...") in caplog.text

        with pytest.raises(KeyError) as excinfo:
            _ = RedisStorage(namespace = 23) # type: ignore
        msg = f"A non-empty namespace string must be provided for the RedisStorage. Received {type(23)}"

        assert msg in caplog.text
        assert msg in str(excinfo.value)

        caplog.clear()
        with pytest.raises(KeyError) as excinfo:
            _ = RedisStorage(namespace = '') # type: ignore
        msg = f"A non-empty namespace string must be provided for the RedisStorage. Received {type('')}"

        assert msg in caplog.text
        assert msg in str(excinfo.value)

    finally:
        redis_test_storage.namespace = current_namespace
        RedisStorage.DEFAULT_NAMESPACE = default_namespace

