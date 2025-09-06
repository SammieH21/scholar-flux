import pytest
from unittest.mock import Mock
from requests import Response
from scholar_flux.data_storage.null_storage import NullStorage
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage import DataCacheManager


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "in_memory_test_storage",
    ],
)
def test_basic_cache_operations(
    request, storage_type, mock_response, mock_cache_storage_data, db_dependency_unavailable
):
    """Test basic cache operations with different storage types."""
    # Create cache manager with specific storage

    dependency_name = storage_type.split("_")[0] if not storage_type.startswith("sql") else "sqlalchemy"
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)

    cache_manager = DataCacheManager(storage)

    # Test cache key generation
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)
    assert isinstance(cache_key, str)
    assert len(cache_key) > 0

    # Test update cache
    cache_manager.update_cache(
        cache_key=cache_key,
        response=mock_response,
        parsed_response=mock_cache_storage_data["parsed_response"],
        processed_response=mock_cache_storage_data["processed_response"],
        metadata=mock_cache_storage_data["metadata"],
    )

    # Test verify cache - the cache should be working given that a Null Test Storage is not being used
    cached = storage_type != "null_test_storage"
    assert cache_manager.verify_cache(cache_key) is cached
    assert cache_manager.verify_cache("nonexistent_key") is False

    # Test retrieve
    retrieved = cache_manager.retrieve(cache_key)
    assert retrieved is not None
    assert retrieved["parsed_response"] == mock_cache_storage_data["parsed_response"]
    assert retrieved["processed_response"] == mock_cache_storage_data["processed_response"]

    retrieved_all = cache_manager.retrieve(cache_key)
    assert retrieved_all
    assert retrieved["parsed_response"] == retrieved_all.get("parsed_response")
    assert retrieved["processed_response"] == retrieved_all.get("processed_response")

    # Test cache validity
    assert cache_manager.cache_is_valid(cache_key, mock_response) is True

    # Test delete
    cache_manager.delete(cache_key)
    assert cache_manager.verify_cache(cache_key) is False


def test_null_storage_behavior(mock_response):
    """Test DataCacheManager with NullStorage."""
    cache_manager = DataCacheManager(NullStorage())

    # Should not store anything
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)

    # All operations should return False/None without error
    assert cache_manager.verify_cache(cache_key) is False
    assert cache_manager.cache_is_valid(cache_key, mock_response) is False
    assert cache_manager.retrieve(cache_key) == {}

    # Update should not raise errors
    cache_manager.update_cache(cache_key=cache_key, response=mock_response, parsed_response={"test": "data"})

    # Retrieve should still return empty dict
    assert cache_manager.retrieve(cache_key) == {}


def test_factory_methods():
    """Test factory methods for creating DataCacheManager with different storages."""
    # Test null storage
    null_cache = DataCacheManager.null()
    assert isinstance(null_cache.cache_storage, NullStorage)

    # Test inmemory storage
    inmemory_cache = DataCacheManager.with_storage("inmemory")
    assert isinstance(inmemory_cache.cache_storage, InMemoryStorage)

    # Test invalid storage
    with pytest.raises(Exception):  # StorageCacheException expected
        DataCacheManager.with_storage("invalid_storage")  # type: ignore


def test_bool_operator():
    """Test the __bool__ operator."""
    # Null storage should return False
    null_cache = DataCacheManager.null()
    assert bool(null_cache) is False

    # InMemory storage should return True
    inmemory_cache = DataCacheManager.with_storage("inmemory")
    assert bool(inmemory_cache) is True


def test_cache_with_different_response_hashes(mock_response):
    """Test cache validation with different response hashes."""
    cache_manager = DataCacheManager(InMemoryStorage())
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)

    # Update with first response
    cache_manager.update_cache(cache_key=cache_key, response=mock_response, processed_response={"original": True})

    # Cache should be valid initially
    assert cache_manager.cache_is_valid(cache_key, mock_response) is True

    # Create a new response with different content
    new_response = Mock(spec=Response)
    new_response.url = "https://api.example.com/test"
    new_response.status_code = 200
    new_response.content = b"different content"

    # Cache should no longer be valid with different content
    assert cache_manager.cache_is_valid(cache_key, new_response) is False


def test_cache_retrieval_with_none_data(mock_response):
    """Test cache retrieval when data is None or empty."""
    cache_manager = DataCacheManager(InMemoryStorage())
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)

    # Test retrieving non-existent key
    result = cache_manager.retrieve(cache_key)
    assert isinstance(result, dict)

    # Test with actual data
    cache_manager.update_cache(cache_key=cache_key, response=mock_response, parsed_response=None, processed_response={})

    retrieved = cache_manager.retrieve(cache_key)
    assert retrieved
    assert retrieved["parsed_response"] is None
    assert retrieved["processed_response"] == {}


def test_delete_nonexistent_key(mock_response):
    """Test deleting a key that doesn't exist."""
    cache_manager = DataCacheManager(InMemoryStorage())
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)

    # Should not raise an exception when deleting non-existent key
    try:
        cache_manager.delete(cache_key)
    except Exception as e:
        pytest.fail(f"Delete should not raise exception for non-existent key: {e}")
