import pytest
from scholar_flux.data_storage import DataCacheManager
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage.null_storage import NullStorage
from datetime import datetime, timezone
from time import sleep
import re


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "mongo_nm_test_storage",
        "sqlite_test_storage",
        "sqlite_nm_test_storage",
        "in_memory_test_storage",
        "in_memory_nm_test_storage",
    ],
)
def test_basic_cache_manager_operations(
    request, storage_type, db_dependency_unavailable, mock_response, mock_cache_storage_data, caplog
):
    """Test basic cache operations with different storage types."""
    # Create cache manager with specific storage
    dependency_name = storage_type.split("_")[0] if not storage_type.startswith("sql") else "sqlalchemy"
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)
    storage.delete_all()
    # Test cache key generation
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    assert re.search(f"Generated fallback cache key: {cache_key}", caplog.text) is not None
    assert isinstance(cache_key, str)
    assert len(cache_key) > 0

    # Test update cache
    storage.update(
        key=cache_key,
        data=dict(
            response=mock_response.content,
            parsed_response=mock_cache_storage_data["parsed_response"],
            processed_records=mock_cache_storage_data["processed_records"],
            metadata=mock_cache_storage_data["metadata"],
        ),
    )

    # Test verify cache
    assert storage.verify_cache(cache_key) is True
    assert storage.verify_cache("nonexistent_key") is False

    # Test retrieve
    retrieved = storage.retrieve(cache_key)
    assert retrieved is not None
    assert retrieved["parsed_response"] == mock_cache_storage_data["parsed_response"]
    assert retrieved["processed_records"] == mock_cache_storage_data["processed_records"]

    # Test delete
    storage.delete(cache_key)
    assert storage.verify_cache(cache_key) is False

    keys = []
    for i in range(3):
        updated_cache_key = cache_key + f"_{i}"
        keys.append(
            f"{storage.namespace + ':' if hasattr(storage, 'namespace') and storage.namespace else ''}{updated_cache_key}"
        )
        storage.update(
            key=updated_cache_key,
            data=dict(
                response=mock_response.content,
                parsed_response=mock_cache_storage_data["parsed_response"],
                processed_records=mock_cache_storage_data["processed_records"],
                metadata=mock_cache_storage_data["metadata"],
            ),
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
    assert null_test_storage.retrieve(cache_key) is None

    # Update should not raise errors
    null_test_storage.update(key=cache_key, data=dict(response=mock_response.content, parsed_response={"test": "data"}))

    # Retrieve should still return None
    assert null_test_storage.retrieve(cache_key) is None


@pytest.mark.parametrize(
    "storage_type",
    ["redis_test_storage", "mongo_test_storage", "sqlite_test_storage", "in_memory_test_storage", "null_test_storage"],
)
def test_bool_operator(request, storage_type, db_dependency_unavailable):
    """Test the __bool__ operator to verify whether all implementations other than the No-Op storage are truthy."""

    dependency_name = storage_type.split("_")[0] if not storage_type.startswith("sql") else "sqlalchemy"
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)

    # Only Null storage should return False
    if storage_type == "null_test_storage":
        assert bool(storage) is False
    else:
        assert bool(storage) is True


@pytest.mark.parametrize(
    "storage_type",
    ["redis_test_storage", "mongo_test_storage", "sqlite_test_storage", "in_memory_test_storage", "null_test_storage"],
)
def test_basic_instance_structure(storage_type, request):
    """Verifies that all methods have the same set of fundamental variable names in their namespace.

    If any of the storage devices do not have a class/instance variable, it should raise a NameError.

    """
    storage = request.getfixturevalue(storage_type)
    assert storage.DEFAULT_NAMESPACE is None or isinstance(storage.DEFAULT_NAMESPACE, str)
    assert isinstance(storage.DEFAULT_RAISE_ON_ERROR, bool)
    assert isinstance(storage.raise_on_error, bool)
    assert isinstance(storage.ttl, float) or storage.ttl is None
    assert storage.namespace is None or isinstance(storage.namespace, str)


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "in_memory_test_storage",
    ],
)
def test_cache_retrieval_with_none_data(request, mock_response, storage_type, db_dependency_unavailable):
    """Test cache retrieval when data is None or empty."""

    dependency_name = storage_type.split("_")[0] if not storage_type.startswith("sql") else "sqlalchemy"
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)
    assert storage.is_available()
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)

    # Test retrieving non-existent key
    result = storage.retrieve(cache_key)
    assert result is None

    # Test with actual data
    storage.update(key=cache_key, data=dict(response=mock_response.content, parsed_response=None, processed_records={}))

    retrieved = storage.retrieve(cache_key)
    assert retrieved
    assert retrieved["parsed_response"] is None
    assert retrieved["processed_records"] == {}


def test_redis_expiration(redis_test_storage):
    """Verifies that cached Redis records successfully remove expired records after a certain interval of time."""
    key = "some_temp_key"
    value = {"data": "some_temp_value"}

    try:
        previous_ttl = redis_test_storage.ttl
        redis_test_storage.ttl = 1
        redis_test_storage.update(key, value)
        sleep(1.1)
        assert redis_test_storage.verify_cache(key) is False
        redis_test_storage.ttl = previous_ttl
    finally:
        redis_test_storage.delete(key)


def test_mongo_expiration(mongo_test_storage):
    """Verifies that cached MongoDB records successfully remove expired records after a certain interval of time."""
    key = "some_temp_key"
    value = {"data": "some_temp_value"}

    try:
        previous_ttl = mongo_test_storage.ttl
        mongo_test_storage.ttl = 0.5
        mongo_test_storage.update(key, value)
        doc = mongo_test_storage.collection.find_one({"key": mongo_test_storage._prefix(key)})
        assert doc is not None
        assert "expireAt" in doc
        # Optionally, check that expireAt is within a reasonable range
        expire_at = doc["expireAt"].replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        assert 0 < (expire_at - now).total_seconds() <= 1.5
        mongo_test_storage.ttl = previous_ttl
    finally:
        mongo_test_storage.delete(key)


def test__memory_storage_initialization(caplog):
    """Verifies whether the basic in-memory storage can be initialized and used as a basic storage cache."""
    namespace = "mem"
    memory_storage = InMemoryStorage(namespace=namespace, ttl=1000, raise_on_error=True)  # type:ignore
    assert memory_storage.namespace == namespace
    assert not memory_storage.ttl and not memory_storage.raise_on_error

    assert "The parameter, `raise_on_error` is not enforced in InMemoryStorage. Skipping." in caplog.text
    assert "The parameter, `ttl` is not enforced in InMemoryStorage. Skipping." in caplog.text


def test_memory_cache_deletion_edge_case(caplog):
    """Tests the handling of an unexpected deletion scenario given the complexity of `delete_all` with a namespace."""

    memory_storage = InMemoryStorage()
    # like much of python, objects can be forced into unexpected behavior
    memory_storage.memory_cache = 1000  # type: ignore
    memory_storage.delete_all()
    assert "An error occurred deleting e: object of type 'int' has no len()" in caplog.text


@pytest.mark.parametrize("value", ([], [1, 2, 3], {}, None, ""))
def test_unexpected_memory_cache_verification_input(value, in_memory_test_storage, caplog):
    """Tests unexpected inputs to `InMemoryStorage.verify_cache`."""

    with pytest.raises((KeyError, TypeError)):
        _ = in_memory_test_storage.verify_cache(value)  # type: ignore


@pytest.mark.parametrize(
    "data",
    (
        b"hello world",
        None,
        -1e20,
        0,
        0.0,
        1e50,
        True,
        False,
        "hello world",
        ["hello", "world"],
        {"hello": "world"},
        {"hello": b"world"},
        {"hello": [b"world", "!"]},
        {"a": b"bytes", "b": "string", "c": None, "d": [b"ListBytes", "ListStr", None]},
    ),
)
def test_roundtrip_deserialization(data, sqlite_test_storage):
    """Verifies that roundtrip encoding and decoding JSON with the `SQLAlchemyStorage` produces the original data.

    The `_serialize_data` and `_deserialize_data`  methods of the `SQLAlchemyStorage` both use the `JSONDataEncoder` to
    recursively encode and decode raw json data in preparation for JSON data storage and retrieval  in SQL.

    This test verifies that, with unexpected data types, the `SQLAlchemyStorage` will still serialize and deserialize
    the inputted JSON data to produce the original value.

    """

    serialized_data = sqlite_test_storage._serialize_data(data)
    assert sqlite_test_storage._deserialize_data(serialized_data) == data


def test_no_operation_null_storage(caplog):
    """Verifies whether the NullStorage (NoOp) can be initialized without error while ignoring basic parameters."""
    namespace = "NoOp"
    null_storage = NullStorage(namespace=namespace, ttl=1000, raise_on_error=True)  # type:ignore

    assert null_storage.namespace is None
    assert not null_storage.ttl and not null_storage.raise_on_error
    null_storage._initialize()  # should do nothing at all

    assert "The parameter, `namespace` is not enforced in NullStorage. Skipping." in caplog.text
    assert "The parameter, `raise_on_error` is not enforced in NullStorage. Skipping." in caplog.text
    assert "The parameter, `ttl` is not enforced in NullStorage. Skipping." in caplog.text

    key = "some_key"
    null_storage.update(key, "value")
    assert null_storage.retrieve_keys() == []
    assert null_storage.retrieve(key) is None
    assert null_storage.retrieve_all() == {}
    null_storage.delete(key)
    null_storage.delete_all()
    assert null_storage.verify_cache(key) is False
    assert null_storage.is_available() is True
    assert not null_storage


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "in_memory_test_storage",
    ],
)
def test_delete_nonexistent_key(request, mock_response, storage_type, db_dependency_unavailable):
    """Test deleting a key that doesn't exist."""

    dependency_name = storage_type.split("_")[0] if not storage_type.startswith("sql") else "sqlalchemy"
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)

    # Should not raise an exception when deleting non-existent key
    try:
        storage.delete(cache_key)
    except Exception as e:
        pytest.fail(f"Delete should not raise exception for non-existent key: {e}")
