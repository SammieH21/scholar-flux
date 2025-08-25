import pytest


import pytest
from unittest.mock import Mock, patch
from requests import Response
from scholar_flux.data_storage.null_storage import NullStorage
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage.sql_storage import SQLAlchemyStorage
from scholar_flux.data_storage.mongodb_storage import MongoDBStorage
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.data_storage import DataCacheManager


@pytest.mark.parametrize("storage", [
    'redis_test_storage', 
    'mongo_test_storage',
    'mongo_nm_test_storage',
    'sqlite_test_storage',
    'sqlite_nm_test_storage',
    'in_memory_test_storage',
    'in_memory_nm_test_storage',
])
def test_basic_cache_manager_operations(request, storage, mock_response, mock_cache_storage_data):
    """Test basic cache operations with different storage types."""
    # Create cache manager with specific storage
    storage = request.getfixturevalue(storage)
    storage.delete_all()
    # Test cache key generation
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    assert isinstance(cache_key, str)
    assert len(cache_key) > 0

    # Test update cache
    storage.update(
        key=cache_key,
        data=dict(response=mock_response.content,
                  parsed_response=mock_cache_storage_data['parsed_response'],
                  processed_response=mock_cache_storage_data['processed_response'],
                  metadata=mock_cache_storage_data['metadata'])
    )

    # Test verify cache
    assert storage.verify_cache(cache_key) is True
    assert storage.verify_cache("nonexistent_key") is False

    # Test retrieve
    retrieved = storage.retrieve(cache_key)
    assert retrieved is not None
    assert retrieved['parsed_response'] == mock_cache_storage_data['parsed_response']
    assert retrieved['processed_response'] == mock_cache_storage_data['processed_response']


    # Test delete
    storage.delete(cache_key)
    assert storage.verify_cache(cache_key) is False

    keys=[]
    for i in range(3):
        updated_cache_key = cache_key + f'_{i}'
        keys.append(f"{storage.namespace + ':' if hasattr(storage, 'namespace') and storage.namespace else ''}{updated_cache_key}")
        storage.update(
            key=updated_cache_key,
            data = dict(
                response=mock_response.content,
                parsed_response=mock_cache_storage_data['parsed_response'],
                processed_response=mock_cache_storage_data['processed_response'],
                metadata=mock_cache_storage_data['metadata']
            )
             )
    assert len(storage.retrieve_all()) == 3
    assert not set(keys).symmetric_difference(storage.retrieve_keys())
    storage.delete_all()
    assert [] == storage.retrieve_keys()
    assert len(storage.retrieve_all()) == 0
    storage.delete_all()



def test_null_storage_behavior(mock_response, null_test_storage):
    """Test DataCacheManager with NullStorage."""
    
    # Should not store anything
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    
    # All operations should return False/None without error
    assert null_test_storage.verify_cache(cache_key) is False
    assert null_test_storage.retrieve(cache_key) == None
    
    # Update should not raise errors
    null_test_storage.update(
        key=cache_key,
        data=dict(response=mock_response.content,
                  parsed_response={'test': 'data'}
                 )
    )
    
    # Retrieve should still return None
    assert null_test_storage.retrieve(cache_key) == None

@pytest.mark.parametrize("storage_type", [
    'redis_test_storage', 
    'mongo_test_storage',
    'sqlite_test_storage',
    'in_memory_test_storage',
    'null_test_storage'
])
def test_bool_operator(request, storage_type):
    """Test the __bool__ operator."""
    storage = request.getfixturevalue(storage_type)

    # Only Null storage should return False
    if storage_type == 'null_test_storage':
        assert bool(storage) is False
    else:
        assert bool(storage) is True

@pytest.mark.parametrize("storage_type", [
    'redis_test_storage', 
    'mongo_test_storage',
    'sqlite_test_storage',
    'in_memory_test_storage',
])
def test_cache_retrieval_with_none_data(request, mock_response, storage_type):
    """Test cache retrieval when data is None or empty."""

    storage = request.getfixturevalue(storage_type)
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    
    # Test retrieving non-existent key
    result = storage.retrieve(cache_key)
    assert result is None
    
    # Test with actual data
    storage.update(
        key=cache_key,
        data=dict(
            response=mock_response.content,
            parsed_response=None,
            processed_response={}
        )
    )
    
    retrieved = storage.retrieve(cache_key)
    assert retrieved
    assert retrieved['parsed_response'] is None
    assert retrieved['processed_response'] == {}

@pytest.mark.parametrize("storage_type", [
    'redis_test_storage', 
    'mongo_test_storage',
    'sqlite_test_storage',
    'in_memory_test_storage',
])
def test_delete_nonexistent_key(request, mock_response, storage_type):
    """Test deleting a key that doesn't exist."""
    storage = request.getfixturevalue(storage_type)
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    
    # Should not raise an exception when deleting non-existent key
    try:
        storage.delete(cache_key)
    except Exception as e:
        pytest.fail(f"Delete should not raise exception for non-existent key: {e}")

