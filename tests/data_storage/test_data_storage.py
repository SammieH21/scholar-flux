import re
from datetime import datetime, timezone
from time import sleep
from unittest.mock import patch

import pytest

from scholar_flux.data_storage import DataCacheManager
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage.mongodb_storage import MongoDBStorage
from scholar_flux.data_storage.null_storage import NullStorage
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.data_storage.sql_storage import DuckDBStorage, SQLAlchemyStorage
from scholar_flux.exceptions import CacheParameterValidationException
from scholar_flux.security import masker
from scholar_flux.utils import config_settings


def test_default_storage_types():
    """Verifies that the names of storage types match their functionality or database implementation."""
    assert RedisStorage.STORAGE_TYPE.upper() == "REDIS"
    assert MongoDBStorage.STORAGE_TYPE.upper() == "MONGODB"
    assert SQLAlchemyStorage.STORAGE_TYPE.upper() == "SQL"
    assert InMemoryStorage.STORAGE_TYPE.upper() == "INMEMORY"
    assert DuckDBStorage.STORAGE_TYPE.upper() == "DUCKDB"


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
        "mongo_nm_test_storage",
        "sqlite_test_storage",
        "sqlite_nm_test_storage",
        "duckdb_test_storage",
        "duckdb_nm_test_storage",
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
    storage.verify_connection()  # should not throw an error if a connection can be successfully established
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)
    assert re.search(f"Generated fallback cache key: {cache_key}", caplog.text) is not None
    assert isinstance(cache_key, str)
    assert len(cache_key) > 0

    data_dict = dict(
        response=mock_response.content,
        parsed_response=mock_cache_storage_data["parsed_response"],
        processed_records=mock_cache_storage_data["processed_records"],
        metadata=mock_cache_storage_data["metadata"],
    )

    # Test update cache
    storage.update(
        key=cache_key,
        data=data_dict,
    )

    # Test verify cache
    assert storage.verify_cache(cache_key) is True
    assert storage.verify_cache("nonexistent_key") is False

    # Test retrieve
    retrieved = storage.retrieve(cache_key)
    assert retrieved is not None
    assert retrieved["parsed_response"] == mock_cache_storage_data["parsed_response"]
    assert retrieved["processed_records"] == mock_cache_storage_data["processed_records"]

    # Test overwrite
    storage.update(key=cache_key, data=data_dict)
    assert retrieved == storage.retrieve(cache_key)

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
    assert storage.retrieve_keys() == []
    assert len(storage.retrieve_all()) == 0
    storage.delete_all()


@pytest.mark.parametrize(
    "storage_type",
    [
        "redis_test_storage",
        "mongo_test_storage",
    ],
)
def test_default_config_equivalence_at_runtime(storage_type, request, db_dependency_unavailable):
    """Verifies that upon loading core scholar-flux, default static and dynamic host and port variables are equal."""
    dependency_name = storage_type.split("_")[0]
    if db_dependency_unavailable(dependency_name):
        pytest.skip()
    storage = request.getfixturevalue(storage_type)

    default_config_dynamic = {
        key: value for key, value in storage.get_default_config().items() if key in ("host", "port")
    }
    default_config_class_variable = {
        key: value for key, value in storage.DEFAULT_CONFIG.items() if key in ("host", "port")
    }

    assert default_config_class_variable == default_config_dynamic


@pytest.mark.parametrize(
    "storage_type,host,port",
    [
        ("redis_test_storage", "SCHOLAR_FLUX_REDIS_HOST", "SCHOLAR_FLUX_REDIS_PORT"),
        ("mongo_test_storage", "SCHOLAR_FLUX_MONGODB_HOST", "SCHOLAR_FLUX_MONGODB_PORT"),
    ],
)
def test_default_config_settings_override(
    storage_type, host, port, request, db_dependency_unavailable, restore_config_settings
):
    """Verifies that updating the host and port manually overrides the `DEFAULT_CONFIG` settings."""
    dependency_name = storage_type.split("_")[0]
    if db_dependency_unavailable(dependency_name):
        pytest.skip()
    storage = request.getfixturevalue(storage_type)

    host_value = "temphostname"
    port_value = 9999

    config_settings.set(host, host_value)
    config_settings.set(port, port_value)

    default_config = storage.get_default_config()
    assert default_config["host"] == host_value
    assert default_config["port"] == port_value


@patch("redis.Redis")
def test_redis_username_password_retrieval(mock_redis_client, db_dependency_unavailable, mock_api_key, monkeypatch):
    """Verifies that Redis builds a dictionary containing authentication parameters when available."""
    if db_dependency_unavailable("redis"):
        pytest.skip()
    user = "admin"
    username_env = "SCHOLAR_FLUX_REDIS_USERNAME"
    password_env = "SCHOLAR_FLUX_REDIS_PASSWORD"

    with monkeypatch.context() as m:
        m.setenv(username_env, user)
        m.setenv(password_env, masker.unmask_secret(mock_api_key))  # pretend its an actual password

        config = RedisStorage.get_default_config()
        assert config.get("username") == masker.mask_secret(user)
        assert config.get("password") == mock_api_key  # API key already masked
        config.pop("ttl", None)
        unmasked_config = masker.unmask_parameters(config)

        _ = RedisStorage()
        mock_redis_client.assert_called_with(
            host=unmasked_config["host"],
            port=unmasked_config["port"],
            username=unmasked_config["username"],
            password=unmasked_config["password"],
        )

    # Fields should only show if they've been stored in the config or environment. Context over
    config = RedisStorage.get_default_config()
    assert "username" not in config
    assert "password" not in config


@patch("scholar_flux.data_storage.mongodb_storage.MongoClient")
def test_mongodb_username_password_retrieval(mock_mongodb_client, db_dependency_unavailable, mock_api_key, monkeypatch):
    """Verifies that MongoDB builds a dictionary containing authentication parameters when available."""
    if db_dependency_unavailable("mongodb"):
        pytest.skip()
    user = "admin"
    username_env = "SCHOLAR_FLUX_MONGODB_USERNAME"
    password_env = "SCHOLAR_FLUX_MONGODB_PASSWORD"

    with monkeypatch.context() as m:
        m.setenv(username_env, user)
        m.setenv(password_env, masker.unmask_secret(mock_api_key))  # pretend its an actual password

        config = MongoDBStorage.get_default_config()
        assert config.get("username") == masker.mask_secret(user)
        assert config.get("password") == mock_api_key  # API key already masked

        _ = MongoDBStorage()
        mock_mongodb_client.assert_called_with(
            host=config["host"],
            port=config["port"],
            serverSelectionTimeoutMS=config["serverSelectionTimeoutMS"],
            username=masker.unmask_secret(config["username"]),
            password=masker.unmask_secret(config["password"]),
        )

    # Fields should only show if they've been stored in the config or environment. Context over
    config = MongoDBStorage.get_default_config()
    assert "username" not in config
    assert "password" not in config


@patch("scholar_flux.data_storage.mongodb_storage.MongoClient")
def test_mongodb_username_password_availability_check(
    mock_mongodb_client, restore_config_settings, db_dependency_unavailable, mock_api_key, monkeypatch
):
    """Verifies that MongoDB builds a dictionary containing authentication parameters when available."""
    if db_dependency_unavailable("mongodb"):
        pytest.skip()

    user = masker.mask_secret("admin")

    config_settings.set("SCHOLAR_FLUX_MONGODB_USERNAME", user)
    config_settings.set("SCHOLAR_FLUX_MONGODB_PASSWORD", mock_api_key)

    MongoDBStorage.is_available()

    _, kwargs = mock_mongodb_client.call_args
    assert kwargs["username"] == masker.unmask_secret(user)
    assert kwargs["password"] == masker.unmask_secret(mock_api_key)


@patch("redis.Redis")
def test_redis_username_password_availability_check(
    mock_redis_client, restore_config_settings, db_dependency_unavailable, mock_api_key, monkeypatch
):
    """Verifies that redis builds a dictionary containing authentication parameters when available."""
    if db_dependency_unavailable("redis"):
        pytest.skip()

    user = masker.mask_secret("admin")

    config_settings.set("SCHOLAR_FLUX_REDIS_USERNAME", user)
    config_settings.set("SCHOLAR_FLUX_REDIS_PASSWORD", mock_api_key)

    RedisStorage.is_available()

    _, kwargs = mock_redis_client.call_args
    assert kwargs["username"] == masker.unmask_secret(user)
    assert kwargs["password"] == masker.unmask_secret(mock_api_key)


def test_null_storage_behavior(mock_response, null_test_storage):
    """Test DataCacheManager with NullStorage."""

    # Should not store anything
    cache_key = DataCacheManager.generate_fallback_cache_key(mock_response)

    # All operations should return False/None without error
    assert null_test_storage.verify_cache(cache_key) is False
    assert null_test_storage.retrieve(cache_key) is None
    assert null_test_storage.verify_connection() is None

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
    [
        "redis_test_storage",
        "mongo_test_storage",
        "sqlite_test_storage",
        "duckdb_test_storage",
        "in_memory_test_storage",
        "null_test_storage",
    ],
)
def test_basic_instance_structure(storage_type, request, db_dependency_unavailable):
    """Verifies that all methods have the same set of fundamental variable names in their namespace.

    If any of the storage devices do not have a class/instance variable, it should raise a NameError.

    """
    dependency_name = storage_type.split("_")[0] if not storage_type.startswith("sql") else "sqlalchemy"
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    storage = request.getfixturevalue(storage_type)
    assert storage.DEFAULT_NAMESPACE is None or isinstance(storage.DEFAULT_NAMESPACE, str)
    assert isinstance(storage.DEFAULT_RAISE_ON_ERROR, bool)
    assert isinstance(storage.raise_on_error, bool)
    assert isinstance(storage.ttl, float) or storage.ttl is None
    assert storage.namespace is None or isinstance(storage.namespace, str)


def test_ttl_warn(sqlite_test_storage, caplog):
    """Verifies that a warning is thrown when a user attempts to use ttl expiration cache with sqlalchemy."""
    SQLAlchemyStorage(**sqlite_test_storage.config, ttl=3)  # type: ignore
    assert "TTL is not enabled for SQLAlchemyStorage. Skipping" in caplog.text


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


def test_redis_expiration(redis_test_storage, db_dependency_unavailable):
    """Verifies that cached Redis records successfully remove expired records after a certain interval of time."""
    if db_dependency_unavailable("redis"):
        pytest.skip()

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


def test_redis_set_ttl_no_expire(redis_test_storage, db_dependency_unavailable, restore_config_settings):
    """Verifies that Redis uses a TTL that foregoes expiration when `SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL=-1`."""
    if db_dependency_unavailable("redis"):
        pytest.skip()

    config_settings.set("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL", -1)
    redis_verification_storage = RedisStorage(**redis_test_storage.config)
    assert redis_verification_storage.ttl is None


def test_mongodb_set_ttl_no_expire(mongo_test_storage, db_dependency_unavailable, restore_config_settings):
    """Verifies that MongoDB uses a TTL that foregoes expiration when `SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL=-1`."""
    if db_dependency_unavailable("mongodb"):
        pytest.skip()

    config_settings.set("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL", -1)
    mongodb_verification_storage = MongoDBStorage(**mongo_test_storage.config)
    assert mongodb_verification_storage.ttl is None


def test_mongodb_invalid_ttl(mongo_test_storage, db_dependency_unavailable):
    """Verifies that MongoDBStorage raises a CacheParameterValidationException when an invalid TTL value is provided."""
    if db_dependency_unavailable("mongodb"):
        pytest.skip()

    invalid_ttl = -2
    with pytest.raises(CacheParameterValidationException) as excinfo:
        _ = MongoDBStorage(ttl=invalid_ttl, **mongo_test_storage.config)
    assert (
        f"The {MongoDBStorage.__name__} expected the TTL to be a non-negative number, `None`, or -1 (no expiration), but "
        f"received an invalid value ({invalid_ttl})"
    ) in str(excinfo.value)


def test_redis_invalid_ttl(redis_test_storage, db_dependency_unavailable):
    """Verifies that RedisStorage raises a CacheParameterValidationException when an invalid TTL value is provided."""
    if db_dependency_unavailable("redis"):
        pytest.skip()

    invalid_ttl = -1.1
    with pytest.raises(CacheParameterValidationException) as excinfo:
        _ = RedisStorage(ttl=invalid_ttl, **redis_test_storage.config)  # type: ignore
    assert (
        f"The {RedisStorage.__name__} expected the TTL to be a non-negative number, `None`, or -1 (no expiration), but "
        f"received an invalid value ({invalid_ttl})"
    ) in str(excinfo.value)


@pytest.mark.parametrize(
    "cls_ttl,env_ttl,instance_ttl,expected",
    (
        (60, None, None, 60),  # cls var is the default
        (1, 2, None, 2),  # env overrides cls
        (None, None, 1, 1),  # instance var overrides
        (None, 1, None, 1),  # an available env var overrides None
        (0, -1, 2, 2),  # an available instance var overrides cls + env
        (None, 1, -1, None),  # env = -1 turns off cache when instance var is None
        (1, 3, 5, 5),  #  Instance var should override
    ),
)
def test_redis_ttl_resolution_order(
    cls_ttl,  # default
    env_ttl,  # override
    instance_ttl,  # overrides the env when not None
    expected,
    db_dependency_unavailable,
    redis_test_storage,
    restore_config_settings,
    monkeypatch,
):
    """Verifies that Redis devices correctly resolve TTLs from env, class, and instance-level settings."""
    if db_dependency_unavailable("redis"):
        pytest.skip()

    with monkeypatch.context() as m:
        m.setitem(RedisStorage.DEFAULT_CONFIG, "ttl", cls_ttl)
        m.setenv("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL", env_ttl)
        config_settings.set("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL", env_ttl)
        storage = RedisStorage(ttl=instance_ttl, **redis_test_storage.config)
        assert storage.ttl == expected


@pytest.mark.parametrize(
    "cls_ttl,env_ttl,instance_ttl,expected",
    (
        (2, None, None, 2),
        (2, 3, None, 3),  # env var overrides cls var
        (None, 1, 2, 2),  # instance overrides env var
        (None, 2, None, 2),
        (None, -1, 1, 1),
        (None, 1, -1, None),
        (-1, 2, 3, 3),
    ),
)
def test_mongodb_ttl_resolution_order(
    cls_ttl,  # default
    env_ttl,  # override
    instance_ttl,  # overrides the env when not None
    expected,
    db_dependency_unavailable,
    mongo_test_storage,
    restore_config_settings,
    monkeypatch,
):
    """Verifies that MongoDBStorage devices correctly resolve TTLs from env, class, and instance-level settings."""
    if db_dependency_unavailable("mongodb"):
        pytest.skip()

    with monkeypatch.context() as m:
        m.setitem(MongoDBStorage.DEFAULT_CONFIG, "ttl", cls_ttl)
        m.setenv("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL", env_ttl)
        config_settings.set("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL", env_ttl)
        storage = MongoDBStorage(ttl=instance_ttl, **mongo_test_storage.config)
        assert storage.ttl == expected


def test_mongo_expiration(mongo_test_storage, db_dependency_unavailable):
    """Verifies that cached MongoDB records successfully remove expired records after a certain interval of time."""
    if db_dependency_unavailable("mongodb"):
        pytest.skip()

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

    The `_serialize_data` and `_deserialize_data`  methods of the `SQLAlchemyStorage` both use the `JsonDataEncoder` to
    recursively encode and decode raw json data in preparation for JSON data storage and retrieval in SQL.

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
        "duckdb_test_storage",
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


@pytest.mark.parametrize(
    "storage_class",
    [
        RedisStorage,
        MongoDBStorage,
    ],
)
def test_default_config_class_variable_override(storage_class, db_dependency_unavailable, monkeypatch):
    """Verifies that modifying DEFAULT_CONFIG at class level affects get_default_config()."""
    dependency_name = storage_class.__name__.replace("Storage", "").lower()
    if db_dependency_unavailable(dependency_name):
        pytest.skip()

    monkeypatch.setattr("scholar_flux.data_storage.mongodb_storage.config_settings.get", lambda *args, **kwargs: None)
    monkeypatch.setattr("scholar_flux.data_storage.redis_storage.config_settings.get", lambda *args, **kwargs: None)

    # Save original values
    original_host = storage_class.DEFAULT_CONFIG.get("host")
    original_port = storage_class.DEFAULT_CONFIG.get("port")

    try:
        # Modify class-level DEFAULT_CONFIG
        storage_class.DEFAULT_CONFIG["host"] = "custom-host.example.com"
        storage_class.DEFAULT_CONFIG["port"] = 9999

        # Verify get_default_config respects the modification
        default_config = storage_class.get_default_config()
        assert default_config["host"] == "custom-host.example.com"
        assert default_config["port"] == 9999

    finally:
        # Restore original values
        if original_host is not None:
            storage_class.DEFAULT_CONFIG["host"] = original_host
        if original_port is not None:
            storage_class.DEFAULT_CONFIG["port"] = original_port
