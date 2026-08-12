import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scholar_flux.data_storage.sql_storage import (
    DuckDBImportError,
    DuckDBStorage,
    SQLAlchemyImportError,
    SQLAlchemyStorage,
    exc,
)
from scholar_flux.exceptions import (
    CacheDeletionException,
    CacheParameterValidationException,
    CacheRetrievalException,
    CacheUpdateException,
    CacheVerificationException,
    StorageCacheException,
)
from scholar_flux.utils import config_settings
from tests.testing_utilities import raise_error


@pytest.fixture(scope="session", autouse=True)
def skip_missing_sql_dependency(db_dependency_unavailable):
    """Helper fixture for only performing tests for sqlite when sqlite and dependencies are available."""
    if db_dependency_unavailable("sql"):
        pytest.skip()


def test_sqlalchemy_retrieval_error(sqlite_test_storage, caplog):
    """Helper method to test retrieval edge cases with single-record retrieval with SQLite."""
    e = "DB error"
    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = exc.SQLAlchemyError("DB error")
        mock_session_factory.return_value.__enter__.return_value = mock_session
        key = "some_key"
        msg = f"Error during attempted retrieval of key {key} (namespace = '{sqlite_test_storage.namespace}'): {e}"

        result = sqlite_test_storage.retrieve(key)
        assert result is None
        assert msg in caplog.text

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
            _ = sqlite_test_storage.retrieve(key)
        assert msg in str(excinfo.value)


def test_sqlalchemy_retrieve_all_error(sqlite_test_storage, caplog):
    """Helper method to test retrieval edge cases with full-record retrieval with SQLite."""
    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = exc.SQLAlchemyError("DB error")
        mock_session_factory.return_value.__enter__.return_value = mock_session

        result = sqlite_test_storage.retrieve_all()
        assert result == {}
        msg = "Error during attempted retrieval of records from namespace"
        assert msg in caplog.text

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
            _ = sqlite_test_storage.retrieve_all()
        assert msg in str(excinfo.value)


def test_sqlalchemy_retrieve_keys_error(sqlite_test_storage, caplog):
    """Helper method to test retrieval edge cases with key retrieval with SQLite."""
    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.all.side_effect = exc.SQLAlchemyError("DB error")
        mock_session.query.return_value = mock_query
        mock_session_factory.return_value.__enter__.return_value = mock_session

        keys = sqlite_test_storage.retrieve_keys()
        msg = f"Error during attempted retrieval of all keys from namespace '{sqlite_test_storage.namespace}"
        assert keys == []
        assert msg in caplog.text

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheRetrievalException) as excinfo:
            _ = sqlite_test_storage.retrieve_keys()
        assert msg in str(excinfo.value)


def test_sqlalchemy_update_error(sqlite_test_storage, caplog):
    """Tests edge cases involving the `update` method for inserting and updating cached data in SQLite."""
    e = "DB error"
    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = exc.SQLAlchemyError("DB error")
        mock_session_factory.return_value.__enter__.return_value = mock_session

        key = "some_key"
        value = {"data": 1}
        msg = f"Error during attempted update of key {key} (namespace = '{sqlite_test_storage.namespace}'): {e}"
        sqlite_test_storage.update(key, value)
        assert msg in caplog.text

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheUpdateException) as excinfo:
            _ = sqlite_test_storage.update(key, value)
        assert msg in str(excinfo.value)


def test_sqlalchemy_delete_error(sqlite_test_storage, caplog):
    """Tests edge cases involving the `delete` method for removing cached records in SQLite."""
    e = "DB error"
    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = exc.SQLAlchemyError("DB error")
        mock_session_factory.return_value.__enter__.return_value = mock_session

        key = "some_key"
        msg = f"Error during attempted deletion of key {key} (namespace = '{sqlite_test_storage.namespace}'): {e}"
        sqlite_test_storage.delete(key)
        assert msg in caplog.text

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheDeletionException) as excinfo:
            _ = sqlite_test_storage.delete(key)
        assert msg in str(excinfo.value)


def test_sqlalchemy_delete_all_error(sqlite_test_storage, caplog):
    """Tests full-record deletion edge cases within SQLAlchemy."""
    e = "DB error"
    msg = f"Error during attempted deletion of all records from namespace '{sqlite_test_storage.namespace}': {e}"
    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = exc.SQLAlchemyError(e)
        mock_session_factory.return_value.__enter__.return_value = mock_session

        sqlite_test_storage.delete_all()
        assert msg in caplog.text

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheDeletionException) as excinfo:
            _ = sqlite_test_storage.delete_all()
        assert msg in str(excinfo.value)


def test_sqlalchemy_verify_cache_error(sqlite_test_storage, caplog):
    """Verifies that `verify_cache` correctly handles edge cases, raising the correct exceptions when needed."""
    with pytest.raises(ValueError) as excinfo:
        _ = sqlite_test_storage.verify_cache(None)
    assert f"Key invalid. Received {None} (namespace = '{sqlite_test_storage.namespace}')" in str(excinfo.value)

    e = "DB error"
    key = "some_key"
    msg = (
        re.escape(
            f"Error during the verification of the existence of key {key} (namespace = '{sqlite_test_storage.namespace}'):"
        )
        + f".*{e}"
    )

    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = exc.SQLAlchemyError(e)
        mock_session_factory.return_value.__enter__.return_value = mock_session

        result = sqlite_test_storage.verify_cache(key)
        assert result is False
        assert re.search(msg, caplog.text) is not None

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheVerificationException) as excinfo_two:
            _ = sqlite_test_storage.verify_cache(key)
        assert re.search(msg, str(excinfo_two.value)) is not None


def test_sqlalchemy_unavailable(sqlite_test_storage, caplog):
    """Verifies that, when the sqlalchemy package is not installed, an error will be raised."""
    with patch("scholar_flux.data_storage.sql_storage.sqlalchemy", None):
        assert not sqlite_test_storage.is_available()
        assert "The sqlalchemy module is not available" in caplog.text

        with pytest.raises(SQLAlchemyImportError) as excinfo:
            SQLAlchemyStorage()
        assert "Optional Dependency: SQL Alchemy backend is not installed" in str(excinfo.value)
        assert "Please install the 'sqlalchemy' package to use this feature." in str(excinfo.value)


def test_duckdb_unavailable(monkeypatch, caplog):
    """Verifies that, when the DuckDB package is not installed, an error will be raised."""
    monkeypatch.setattr("scholar_flux.data_storage.sql_storage.importlib.util.find_spec", lambda mod: None)

    assert DuckDBStorage.is_available() is False
    assert "The sqlalchemy duckdb_engine is not available" in caplog.text

    with pytest.raises(DuckDBImportError):
        _ = DuckDBStorage()


def test_duckdb_unavailable_at_incorrect_url(db_dependency_unavailable, caplog):
    """Verifies that `is_available` identifies an invalid DB URL as not available."""
    if db_dependency_unavailable("duckdb"):
        pytest.skip()
    invalid_db_url = "duckdb:///"
    assert not DuckDBStorage.is_available(url=invalid_db_url)
    err = f"Expected a path after the duckdb:/// protocol in the URI. Only the scheme was received: {invalid_db_url}"
    assert f"DuckDB is not available for connection at the provided URI: {err}" in caplog.text


@pytest.mark.parametrize(
    "storage_class",
    [SQLAlchemyStorage, DuckDBStorage],
)
def test_is_available_catches_error_on_failed_connection(storage_class, db_dependency_unavailable, monkeypatch, caplog):
    """Verifies unavailable SQL DBs raise exceptions on `raise_on_error=True` and `verify_connection=True`."""
    # Note, the storage type is case sensitive and formatted match the
    storage_type = storage_class.STORAGE_TYPE
    if db_dependency_unavailable(storage_type):
        pytest.skip()

    url_scheme = "sqlite:///" if storage_class is SQLAlchemyStorage else "duckdb:///"
    monkeypatch.setattr(SQLAlchemyStorage, "ping", raise_error(exc.SQLAlchemyError, "Directly raised exception"))
    storage_class.is_available()
    assert f"An active {storage_class.STORAGE_TYPE} service could not be found at {url_scheme}" in caplog.text


@pytest.mark.parametrize(
    "storage_class",
    [DuckDBStorage, SQLAlchemyStorage],
)
def test_verify_connection_error_on_failed_connection(storage_class, monkeypatch, db_dependency_unavailable, caplog):
    """Verifies unavailable SQLAlchemy cache storage devices raise `verify_connection=True`."""
    # Note, the storage type is case insensitive
    storage_type = storage_class.STORAGE_TYPE
    if db_dependency_unavailable(storage_type):
        pytest.skip()
    monkeypatch.setattr(SQLAlchemyStorage, "ping", raise_error(RuntimeError, "Directly raised exception"))
    storage_class_name = storage_class.__name__
    err = f"Could not initialize a connection for the following storage device: {storage_class_name}(.*)"
    with pytest.raises(StorageCacheException, match=err):
        _ = storage_class(verify_connection=True)


def test_sqlalchemy_create_default_url(tmp_path, cleanup, monkeypatch):
    """Verifies that SQLAlchemy can create a valid URL within the default writable package directory."""
    with monkeypatch.context() as m:
        m.setenv("SCHOLAR_FLUX_HOME", str(tmp_path))
        default_sqlalchemy_url = SQLAlchemyStorage.create_default_url()
        SQLAlchemyStorage.verify_url_string(default_sqlalchemy_url)
        assert Path(default_sqlalchemy_url.replace("sqlite:///", "")).parent == tmp_path / "package_cache"
        assert default_sqlalchemy_url.endswith(".sqlite")


def test_duckdb_create_default_url(tmp_path, cleanup, monkeypatch):
    """Verifies that the DuckDBStorage can create a valid URL within the default writable package directory."""
    with monkeypatch.context() as m:
        m.setenv("SCHOLAR_FLUX_HOME", str(tmp_path))
        default_duckdb_url = DuckDBStorage.create_default_url()
        # Should be compatible with both SQLAlchemyStorage and DuckDBStorage
        SQLAlchemyStorage.verify_url_string(default_duckdb_url)
        DuckDBStorage.verify_url_string(default_duckdb_url)
        assert Path(default_duckdb_url.replace("duckdb:///", "")).parent == tmp_path / "package_cache"
        assert default_duckdb_url.endswith(".duckdb")


def test_sqlalchemy_get_config_url(tmp_path, cleanup, monkeypatch, restore_config_settings, caplog):
    """Verifies that the SQLAlchemyStorage defaults to a valid user-configured URL when provided."""
    db_url = "sqlite:///" + str(tmp_path / "custom_db_location.sqlite")
    # raises an error if the configured URI is skipped
    monkeypatch.setattr(
        SQLAlchemyStorage,
        "create_default_url",
        raise_error(RuntimeError, "Directly raised exception"),
    )

    env_var = "SCHOLAR_FLUX_SQLALCHEMY_URL"
    err = f"The environment variable, {env_var}, is not a valid SQLAlchemy URL. Returning the default..."

    config_settings.set(env_var, "None")

    with pytest.raises(RuntimeError):
        _ = SQLAlchemyStorage.get_default_url()
    assert err not in caplog.text

    # Doesn't have a `sqlite:///` schema or any other schema
    config_settings.set(env_var, "a_bad_sqlalchemy_url")
    with pytest.raises(RuntimeError):
        _ = SQLAlchemyStorage.get_default_url()
    assert err in caplog.text

    config_settings.set(env_var, db_url)
    assert SQLAlchemyStorage.get_default_url() == db_url


def test_duckdb_get_config_url(tmp_path, cleanup, monkeypatch, restore_config_settings, caplog):
    """Verifies that the DuckDBStorage defaults to a valid user-configured URL when provided."""
    # raises an error if the configured URI is skipped
    monkeypatch.setattr(
        DuckDBStorage,
        "create_default_url",
        raise_error(RuntimeError, "Directly raised exception"),
    )

    env_var = "SCHOLAR_FLUX_SQLALCHEMY_URL"
    err = f"The environment variable, {env_var}, is not a valid DuckDB URL. Returning the default..."

    config_settings.set(env_var, "None")
    with pytest.raises(RuntimeError):
        _ = DuckDBStorage.get_default_url()

    assert err not in caplog.text

    # duckdb URLs must have duckdb:/// schemas
    bad_url = "sqlite:///an_url_with_a_bad_duckdb_schema"
    config_settings.set(env_var, bad_url)
    with pytest.raises(RuntimeError):
        _ = DuckDBStorage.get_default_url()

    assert err in caplog.text

    db_url = "duckdb:///" + str(tmp_path / "custom_db_location.duckdb")
    config_settings.set(env_var, db_url)
    assert DuckDBStorage.get_default_url() == db_url


def test_sqlalchemy_verify_url_string_invalid_inputs():
    """Verifies that providing a bad URL to `verify_url_string` raises a CacheParameterValidationException."""
    invalid_numeric_url = 46
    err = re.escape(f"Expected a valid SQLAlchemy URI, but received type {type(invalid_numeric_url)}")
    with pytest.raises(CacheParameterValidationException, match=err):
        SQLAlchemyStorage.verify_url_string(invalid_numeric_url)  # type: ignore

    invalid_url_scheme = "sqlite///a/valid/db/path"
    err = (
        "Only URIs with valid SQL protocols are supported (e.g., postgres://, sqlite:///, duckdb:///, etc.). "
        f"Received: '{invalid_url_scheme}'"
    )
    with pytest.raises(CacheParameterValidationException, match=re.escape(err)):
        SQLAlchemyStorage.verify_url_string(invalid_url_scheme)

    invalid_url_path = "sqlite:///"
    err = (
        "Expected a path after the protocol in the SQLAlchemy URI. Only the scheme was received: " f"{invalid_url_path}"
    )
    with pytest.raises(CacheParameterValidationException, match=re.escape(err)):
        SQLAlchemyStorage.verify_url_string(invalid_url_path)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:////tmp/valid_db.sqlite",
        "sqlite:///:memory:",
        "postgresql://myuser:secretpass@localhost:5432/mydb",
        "postgres+psycopg2://admin:pass@localhost/app",
        "mysql://root:password123@localhost:3306/scholar_cache",
        "duckdb:///path/to/analytics/db",
        "mysql://user:pass@localhost/db",
        "postgresql://user:secret@[::1]:5432/db",
    ],
)
def test_sqlalchemy_url_validation(url):
    """Verifies that the SQLAlchemyStorage.verify_url_string() class method correctly validates compatible URLs."""
    SQLAlchemyStorage.verify_url_string(url)


def test_duckdb_verify_url_string_invalid_inputs():
    """Verifies that providing a bad DuckDB URL to `verify_url_string` raises a CacheParameterValidationException."""
    invalid_numeric_url = 23
    err = f"Expected a valid DuckDB URI, but received type {type(invalid_numeric_url)}"
    with pytest.raises(CacheParameterValidationException, match=err):
        DuckDBStorage.verify_url_string(invalid_numeric_url)  # type: ignore

    invalid_url_scheme = "sqlite:////an/invalid/db/path"
    err = f"Only URIs with `duckdb:///' protocols are supported. Received: '{invalid_url_scheme}'"
    with pytest.raises(CacheParameterValidationException, match=err):
        DuckDBStorage.verify_url_string(invalid_url_scheme)

    invalid_url_path = "duckdb:///"
    err = f"Expected a path after the duckdb:/// protocol in the URI. Only the scheme was received: {invalid_url_path}"
    with pytest.raises(CacheParameterValidationException, match=err):
        DuckDBStorage.verify_url_string(invalid_url_path)
