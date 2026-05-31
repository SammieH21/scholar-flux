import pytest
from scholar_flux.data_storage.null_storage import NullStorage
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage.sql_storage import SQLAlchemyStorage, DuckDBStorage
from scholar_flux.data_storage import DataCacheManager, ABCStorage
from scholar_flux.utils import config_settings
from scholar_flux.exceptions import StorageCacheException
from tests.testing_utilities import raise_error
import copy
import re


STORAGE_TYPES: list[str] = ["MEMORY", "REDIS", "MONGODB", "SQL", "DUCKDB", "NULL"]


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "duckdb_test_storage",
        "in_memory_test_storage",
    ],
)
def test_basic_cache_operations(
    request, storage_type, mock_response, mock_cache_storage_data, db_dependency_unavailable
):
    """Tests basic cache operations with different storage types."""
    # Create cache manager with specific storage

    dependency_name = storage_type.split("_")[0]
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)

    cache_manager = DataCacheManager(storage)

    # Verifies the connection to the cache
    cache_manager.verify_connection()

    # Test cache key generation
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)
    assert isinstance(cache_key, str)
    assert len(cache_key) > 0

    # Test update cache
    cache_manager.update_cache(
        cache_key=cache_key,
        response=mock_response,
        parsed_response=mock_cache_storage_data["parsed_response"],
        processed_records=mock_cache_storage_data["processed_records"],
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
    assert retrieved["processed_records"] == mock_cache_storage_data["processed_records"]

    retrieved_all = cache_manager.retrieve(cache_key)
    assert retrieved_all
    assert retrieved["parsed_response"] == retrieved_all.get("parsed_response")
    assert retrieved["processed_records"] == retrieved_all.get("processed_records")

    # Test cache validity
    assert cache_manager.cache_is_valid(cache_key, mock_response) is True

    # Test delete
    cache_manager.delete(cache_key)
    assert cache_manager.verify_cache(cache_key) is False


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "duckdb_test_storage",
        "in_memory_test_storage",
    ],
)
def test_namespace_context_management(
    request, storage_type, mock_response, mock_cache_storage_data, db_dependency_unavailable
):
    """Tests that context switching occurs as needed with all implemented storage types."""
    dependency_name = storage_type.split("_")[0]
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)
    cache_manager = DataCacheManager(storage)

    cache_key = cache_manager.generate_fallback_cache_key(mock_response)
    cache_manager.update_cache(
        cache_key=cache_key,
        response=mock_response,
        parsed_response=mock_cache_storage_data["parsed_response"],
        processed_records=mock_cache_storage_data["processed_records"],
        metadata=mock_cache_storage_data["metadata"],
    )

    # Test namespace context switching
    original_namespace = cache_manager.cache_storage.namespace
    original_length = len(cache_manager.cache_storage.retrieve_keys() or [])

    with cache_manager.cache_storage.with_namespace("empty_namespace_with_no_data"):
        assert len(cache_manager.cache_storage.retrieve_keys() or []) == 0 != original_length

        with cache_manager.cache_storage.with_namespace(original_namespace):  # type: ignore
            assert original_length == len(cache_manager.cache_storage.retrieve_keys() or [])


def test_unused_kwargs_are_ignored_on_storage_specification(caplog):
    """Verifies that additional storage keyword arguments are ignored when passing a direct storage argument."""
    memory_storage = InMemoryStorage(namespace="correct_namespace")
    ignored_namespace = "ignored"
    cache_manager = DataCacheManager(memory_storage, namespace=ignored_namespace)
    assert cache_manager.namespace == "correct_namespace"
    assert (
        "Storage keyword arguments were provided but a cache_storage is already instantiated. keyword arguments will "
        "be ignored."
    ) in caplog.text


def test_missing_cache_key_logs_warning(caplog):
    """Verifies that the DataCacheManager logs when using `DataCacheManager.verify_cache` with `cache_key=None`."""
    cache_manager = DataCacheManager.with_storage("memory")
    assert cache_manager.verify_cache(None) is False
    assert "Cache key is None: No cache lookup was performed." in caplog.text


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_create_storage_creates_correct_storage_device(storage_type, db_dependency_unavailable):
    """Verifies that `DataCacheManager._create_storage` creates a new ABCStorage instance."""
    if db_dependency_unavailable(storage_type):
        pytest.skip()

    cache_storage = DataCacheManager._create_storage(storage_type)
    assert storage_type.lower() in type(cache_storage).__name__.lower()


def test_create_storage_raises_error_on_incorrect_type():
    """Verifies that `DataCacheManager._create_storage` raises a `StorageCacheException` for an invalid storage type."""
    invalid_cache_storage = 234
    err = "The chosen storage device for caching processed responses is not valid. Expected a valid string"
    with pytest.raises(StorageCacheException, match=err):
        _ = DataCacheManager._create_storage(invalid_cache_storage)  # type: ignore


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "duckdb_test_storage",
        "in_memory_test_storage",
    ],
)
def test_property_availability(storage_type, request, db_dependency_unavailable):
    """Verifies that the attributes of cache storage devices are accessible as properties on the DataCacheManager."""
    storage_name = storage_type.split("_")[0]
    if db_dependency_unavailable(storage_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)
    cache_manager = DataCacheManager(storage)

    assert cache_manager._cache_storage is cache_manager.cache_storage
    assert cache_manager.ttl is cache_manager.cache_storage.ttl
    assert cache_manager.namespace is cache_manager.cache_storage.namespace
    assert cache_manager.raise_on_error is cache_manager.cache_storage.raise_on_error
    assert cache_manager.config is cache_manager.cache_storage.config


@pytest.mark.parametrize(
    "storage_type,additional_storage_kwargs",
    [
        ("Redis", dict(port=-1)),
        ("MongoDB", dict(port=-1, serverSelectionTimeoutMS=500)),
    ],
)
def test_port_unavailability_raises_error_on_verify_connection(
    storage_type, additional_storage_kwargs, db_dependency_unavailable, restore_config_settings, caplog
):
    """Tests that unavailable DBs raise StorageCacheExceptions on `raise_on_error=True` and `verify_connection=True`."""
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    env_variable = "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE"
    config_settings.set(env_variable, storage_type)
    # Note, the storage type is case sensitive and formatted match the
    err_pattern = (
        f"A storage cache could not be created with the environment variable '{env_variable}'.*{storage_type}."
    )
    with pytest.raises(StorageCacheException, match=err_pattern):
        _ = DataCacheManager.default_cache_storage(
            raise_on_error=True, verify_connection=True, **additional_storage_kwargs
        )


@pytest.mark.parametrize(
    "storage_type",
    ["duckdb", "sql"],
)
def test_ping_raises_error_on_verify_connection_with_url(
    storage_type, db_dependency_unavailable, restore_config_settings, monkeypatch
):
    """Verifies unavailable SQL DBs raise exceptions on `raise_on_error=True` and `verify_connection=True`."""
    # Note, the storage type is case sensitive and formatted match the
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    env_variable = "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE"
    with monkeypatch.context() as m:
        m.setattr(SQLAlchemyStorage, "ping", raise_error(RuntimeError, "Directly raised exception"))
        m.setenv(env_variable, storage_type)

        err_pattern = (
            f"A storage cache could not be created with the environment variable '{env_variable}'.*{storage_type}."
        )
        with pytest.raises(StorageCacheException, match=err_pattern):
            _ = DataCacheManager.default_cache_storage(raise_on_error=True, verify_connection=True)


@pytest.mark.parametrize(
    "storage_type",
    ["duckdb", "sqlite"],
)
def test_successful_connection_with_url(
    storage_type, tmp_path, cleanup, db_dependency_unavailable, restore_config_settings, monkeypatch
):
    """Verifies successful connection setup for SQL storage devices initialized with a URL."""
    # Note, the storage type is case sensitive and formatted match the
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    env_variable = "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE"
    with monkeypatch.context() as m:
        m.setenv(env_variable, storage_type)

    storage_class = DuckDBStorage if storage_type == "duckdb" else SQLAlchemyStorage
    url = f"{storage_type}:///{tmp_path / 'tmp_cache_storage.db'}"

    cache_manager = DataCacheManager.with_storage(storage_type, url=url, verify_connection=True)
    assert isinstance(cache_manager.cache_storage, storage_class)


@pytest.mark.parametrize(
    "storage_type",
    ["duckdb", "sql"],
)
def test_ping_defaults_to_inmemory_on_verify_connection_with_url(
    storage_type, db_dependency_unavailable, restore_config_settings, monkeypatch, caplog
):
    """Verifies unavailable SQL DBs raise exceptions on `raise_on_error=True` and `verify_connection=True`."""
    # Note, the storage type is case sensitive and formatted match the
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    env_variable = "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE"
    with monkeypatch.context() as m:
        m.setattr(SQLAlchemyStorage, "ping", raise_error(RuntimeError, "Directly raised exception"))
        m.setenv(env_variable, storage_type)

        err_pattern = "A storage cache could not be created"
        storage_device = DataCacheManager.default_cache_storage(raise_on_error=False, verify_connection=True)
        assert isinstance(storage_device, InMemoryStorage)
        assert err_pattern in caplog.text


@pytest.mark.parametrize(
    "storage_type,additional_storage_kwargs",
    [
        ("Redis", dict(port=-1)),
        ("MongoDB", dict(port=-1, serverSelectionTimeoutMS=500)),
    ],
)
def test_unavailability_defaults_on_verify_connection_and_raise_error_false(
    storage_type, additional_storage_kwargs, db_dependency_unavailable, restore_config_settings, caplog
):
    """Tests that `DataCacheManager` can fallback to `memory` on `raise_on_error=False` and `verify_connection=True`."""
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    env_variable = "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE"
    config_settings.set(env_variable, storage_type)
    # Note, the storage type is case sensitive and formatted match the
    err_pattern = rf"A storage cache could not be created with the environment variable '{env_variable}'.*{storage_type}.*Defaulting to `InMemoryStorage`\."
    _ = DataCacheManager.default_cache_storage(
        raise_on_error=False, verify_connection=True, **additional_storage_kwargs
    )
    assert re.search(err_pattern, caplog.text, re.DOTALL)


@pytest.mark.parametrize("invalid_cache", (12345, 0, {}, (1, 2, 3)))
def test_invalid_data_cache_storage_device(invalid_cache):
    """Verifies that a storage cache exception is raised when an incorrect type is received."""
    invalid_cache = 12345
    with pytest.raises(StorageCacheException) as excinfo:
        _ = DataCacheManager(invalid_cache)  # type: ignore

    assert (
        "The chosen storage device for caching processed responses is not valid. Expected a valid subclass of "
        f"the `ABCStorage`, but received type {type(invalid_cache)}."
    ) in str(excinfo.value)


def test_default_cache_storage_device():
    """Verifies that the creation of a DataCacheManager without input makes a simple, default cache."""
    cache_manager = DataCacheManager()
    assert isinstance(cache_manager.cache_storage, ABCStorage)  # generally an InMemoryStorage


def test_data_cache_env_storage_resolution(monkeypatch, caplog):
    """Evaluates whether the DataCacheManager catches and raises the intended error on storage resolution failure."""

    env_variable = "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE"

    with monkeypatch.context() as m:
        m.setenv(env_variable, "null")
        # The Null storage is `falsy`
        assert not DataCacheManager.from_defaults()

        invalid_backend = "mdb"
        m.setenv(env_variable, invalid_backend)

        err = (
            "The chosen storage device does not exist. Expected one of the following:"
            " ['redis', 'sql', 'mongodb', 'inmemory', 'null']"
        )

        # the fallback should be validated before use and raise a warning if the env variable is invalid
        memory_cache_session_fallback = DataCacheManager.from_defaults(raise_on_error=False)
        assert isinstance(memory_cache_session_fallback.cache_storage, InMemoryStorage)
        assert err in caplog.text
        #
        #       # when errors are enabled, validation should occur normally
        with pytest.raises(StorageCacheException) as excinfo:
            _ = DataCacheManager.from_defaults(raise_on_error=True)
        assert err in str(excinfo.value)


def test_null_storage_behavior(mock_response):
    """Verifies that DataCacheManager with a NullStorage device operates as a No-Op."""
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
    """Verifies basic factory methods for creating DataCacheManager with different storages."""
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
    """Tests that the __bool__ operator returns False for the NullStorage and True for the InMemoryStorage device."""
    # Null storage should return False
    null_cache = DataCacheManager.null()
    assert bool(null_cache) is False

    # InMemory storage should return True
    inmemory_cache = DataCacheManager.with_storage("inmemory")
    assert bool(inmemory_cache) is True


def test_cache_retrieval_with_none_data(mock_response):
    """Tests cache retrieval when data is None or empty."""
    cache_manager = DataCacheManager(InMemoryStorage())
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)

    # Test retrieving non-existent key
    result = cache_manager.retrieve(cache_key)
    assert isinstance(result, dict)

    # Test with actual data
    cache_manager.update_cache(cache_key=cache_key, response=mock_response, parsed_response=None, processed_records={})

    retrieved = cache_manager.retrieve(cache_key)
    assert retrieved
    assert retrieved["parsed_response"] is None
    assert retrieved["processed_records"] == {}


def test_delete_nonexistent_key(mock_response):
    """Verifies that attempting to delete a key that doesn't exist will not raise an error."""
    cache_manager = DataCacheManager(InMemoryStorage())
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)

    # Should not raise an exception when deleting non-existent key
    try:
        cache_manager.delete(cache_key)
    except Exception as e:
        pytest.fail(f"Delete should not raise exception for non-existent key: {e}")


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "duckdb_test_storage",
        "in_memory_test_storage",
    ],
)
def test_copy(request, mock_response, storage_type, db_dependency_unavailable):
    """Verifies the behavior of the `clone()` and `copy()` methods with different storage backends."""

    dependency_name = storage_type.split("_")[0] if not storage_type.startswith("sql") else "sqlalchemy"
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)
    cache_manager = DataCacheManager(storage)
    new_cache_manager = copy.copy(cache_manager)
    assert id(new_cache_manager) != id(cache_manager)

    storage = request.getfixturevalue(storage_type)
    cache_manager = DataCacheManager(storage)
    new_cache_manager = cache_manager.clone()
    assert id(new_cache_manager) != id(cache_manager)

    assert id(new_cache_manager.cache_storage) != id(cache_manager.cache_storage)
    if client := getattr(cache_manager.cache_storage, "client", None):
        new_client = getattr(new_cache_manager.cache_storage, "client", None)
        config = getattr(cache_manager.cache_storage, "config", None)
        new_config = getattr(new_cache_manager.cache_storage, "config", None)
        assert id(client) != new_client
        assert config and new_config and id(config) != id(new_config) and config == config

    if memory_cache := getattr(cache_manager.cache_storage, "memory_cache", None):
        new_memory_cache = getattr(new_cache_manager.cache_storage, "memory_cache", None)
        assert id(memory_cache) != id(new_cache_manager.cache_storage.memory_cache)  # type: ignore
        assert memory_cache == new_memory_cache


def test_cache_retrieval_with_faulty_data(monkeypatch, caplog):
    """Tests `DataCacheManager.retrieve` edge case handling when an unexpected error occurs during cache retrieval."""
    data_cache_manager = DataCacheManager.with_storage("memory")
    e = "Memory Storage Error"
    msg = f"Error encountered during attempted retrieval from cache: {e}"  # error re-raised from the DataCacheManager
    monkeypatch.setattr(data_cache_manager.cache_storage, "retrieve", raise_error(StorageCacheException, e))

    with pytest.raises(StorageCacheException) as excinfo:
        data_cache_manager.retrieve(cache_key="a_valid_cache_key")
    assert msg in caplog.text
    assert msg in str(excinfo.value)


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_cache_deletion_without_an_entry(storage_type, db_dependency_unavailable, caplog):
    """Verifies that cache deletion in the absence of an entry is handled gracefully."""
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    cache_manager = DataCacheManager.with_storage(storage_type)
    cache_key = "does not exist"
    if not isinstance(cache_manager.cache_storage, NullStorage):
        cache_manager = DataCacheManager.with_storage(storage_type)  # type: ignore
        cache_manager.delete(cache_key)
        assert f"Record for key {cache_key} (namespace = '{cache_manager.namespace}') does not exist" in caplog.text


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_cache_deletion_with_entry(storage_type, mock_response, db_dependency_unavailable, caplog):
    """Verifies that deletion occurs successfully when the value is associated with a cache key in the data cache."""
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    cache_manager = DataCacheManager.with_storage(storage_type)
    cache_key = "does exist"
    if not isinstance(cache_manager.cache_storage, NullStorage):
        cache_manager.update_cache(cache_key, mock_response)
        cache_manager.delete(cache_key)
        assert f"Key: {cache_key}  (namespace = '{cache_manager.namespace}') successfully deleted" in caplog.text


def test_failed_cache_deletion_exception(monkeypatch, caplog):
    """Verifies that `DataCacheManager.delete` catches, and logs exceptions before raising a `StorageCacheException`."""
    storage_type = "inmemory"
    cache_key = "valid cache key"
    cache_manager = DataCacheManager.with_storage(storage_type)  # type: ignore

    err = "Directly raised exception"
    msg = f"Error encountered during attempted record deletion from cache: {err}"
    monkeypatch.setattr(cache_manager.cache_storage, "delete", raise_error(ConnectionError, err))

    with pytest.raises(StorageCacheException) as excinfo:
        cache_manager.delete(cache_key)

    assert msg in caplog.text
    assert msg in str(excinfo.value)
