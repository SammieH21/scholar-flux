import pytest
import re
from unittest.mock import patch, MagicMock
from scholar_flux.data_storage.sql_storage import SQLAlchemyStorage, SQLAlchemyImportError, exc
from tests.testing_utilities import raise_error
from scholar_flux.exceptions import (
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
)


@pytest.fixture(scope="session", autouse=True)
def skip_missing_sql_dependency(db_dependency_unavailable):
    """Helper fixture for only performing tests for sqlite when sqlite and dependencies are available."""
    if db_dependency_unavailable("sqlalchemy"):
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
    """Tests update edge cases with data retrieval in SQLite."""
    e = "DB error"
    with patch.object(sqlite_test_storage, "Session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = exc.SQLAlchemyError("DB error")
        mock_session_factory.return_value.__enter__.return_value = mock_session

        key = "some_key"
        value = {"data": 1}
        msg = f"Error during attempted update of key {key} (namespace = '{sqlite_test_storage.namespace}': {e}"
        sqlite_test_storage.update(key, value)
        assert msg in caplog.text

        with sqlite_test_storage.with_raise_on_error(), pytest.raises(CacheUpdateException) as excinfo:
            _ = sqlite_test_storage.update(key, value)
        assert msg in str(excinfo.value)


def test_sqlalchemy_delete_error(sqlite_test_storage, caplog):
    """Helper method to test deletion edge cases with data retrieval in SQLite."""
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
    """Tests full-record deletion edge cases with in SQL Alchemy."""
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
    """Tests cache verification edge cases in SQLite."""
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


def test_sqlalchemy_server_unavailable(sqlite_test_storage, caplog):
    """Verifies that the behavior of the SQLAlchemyStorage is as expected when attempting to create a connection."""
    msg = "Won't connect"

    with patch("scholar_flux.data_storage.sql_storage.create_engine", raise_error(exc.SQLAlchemyError, msg)):
        assert not sqlite_test_storage.is_available()
