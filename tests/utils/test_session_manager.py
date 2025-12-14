import pytest
import requests
from requests_cache import CachedSession
from pathlib import Path
import os

import logging

logger = logging.getLogger(__name__)

import scholar_flux.sessions.session_manager as sm
from scholar_flux.utils import config_settings
from scholar_flux.data_storage import RedisStorage, MongoDBStorage
from scholar_flux.exceptions.util_exceptions import (
    SessionCreationError,
    SessionCacheDirectoryError,
    SessionConfigurationError,
)
from tests.testing_utilities import raise_error


def test_session_manager_valid_user_agent():
    """Validates that the user agent can be overridden by direct assignment."""
    mgr = sm.SessionManager(user_agent="test-agent")
    session = mgr.configure_session()
    assert session.headers["User-Agent"] == "test-agent"
    assert "SessionManager(user_agent='test-agent')" in repr(mgr)


def test_session_manager_invalid_user_agent():
    """Tests whether an error will be thrown as expected when a user_agent is left blank."""
    with pytest.raises(SessionCreationError):
        sm.SessionManager(user_agent="")


@pytest.fixture
def restore_config_user_agent_default():
    """Helper fixture temporarily removes the `SCHOLAR_FLUX_DEFAULT_USER_AGENT` config value during test execution."""
    agent_env_var = "SCHOLAR_FLUX_DEFAULT_USER_AGENT"
    config_user_agent = config_settings.config.pop(agent_env_var, None)
    yield
    config_settings.set(agent_env_var, config_user_agent, verbose=False)


def test_session_manager_user_agent_os_override(monkeypatch, restore_config_user_agent_default):
    """Tests whether an error will be thrown as expected when a user_agent is left blank."""
    default_user_agent = "sessions-test-default-user-agent"
    with monkeypatch.context():
        monkeypatch.setenv("SCHOLAR_FLUX_DEFAULT_USER_AGENT", default_user_agent)
        session_manager = sm.SessionManager()
        assert session_manager.user_agent == default_user_agent


def test_session_manager_no_user_agent():
    """Validates whether the user agent, as intended, is automatically specified as python-requests by default."""
    mgr = sm.SessionManager()
    session = mgr.configure_session()
    user_agent = session.headers.get("User-Agent", "")
    user_agent = user_agent.decode() if isinstance(user_agent, bytes) else user_agent
    assert "User-Agent" in session.headers and "python-requests" in user_agent.lower()


def test_cached_session_manager_valid():
    """Validates that the configuration is being set as intended and is accessible via the manager as properties."""
    mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory=Path("/tmp"), backend="sqlite")
    representation = repr(mgr)
    assert mgr.cache_name == "c"
    assert mgr.backend == "sqlite"
    assert mgr.user_agent == "ua"
    assert "CachedSessionManager(" in representation and representation.strip("\n")[-1] == ")"
    assert "kwargs=" in representation and "backend=" in representation and "user_agent=" in representation

    session = mgr.configure_session()
    assert isinstance(session, CachedSession)


@pytest.mark.parametrize(
    "param_overrides",
    [
        {"user_agent": ""},  # user_agent must be provided or None
        {"cache_name": None},  # cache name cannot be None, used by all caches
        {"cache_name": "a/nested/cache"},  # cache name cannot be None, used by all caches
        {"expire_after": -2},  # a negative expire_after (other than -1) should trigger a session creation error
        {"backend": "a-non existent backend"},  # requests_cache.CachedSession must receive a valid backend
        {"backend": ""},  # backend cannot be an empty string
    ],
)
def test_session_manager_invalid(param_overrides):
    """Test potentially common configuration issues that should raise a SessionCreationError including:

        - blank user agents
        - directly specified `NoneType` cache names
        - cache names that contain directory path string delimiters (`/`)
        - negative values for `expire_after`
        - backend values that do not exist
        - directly specified `NoneType` backends

    All scenarios should raise a SessionCreationError.

    """
    with pytest.raises(SessionCreationError):
        # a negative expire_after value should raise a validation error which triggers the session creation error
        params = (
            dict(user_agent="ua", cache_name="c", expire_after=20, cache_directory=Path("/tmp"), backend="sqlite")
            | param_overrides
        )
        sm.CachedSessionManager(**params)


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0, reason="Test requires non-root user (root can write anywhere)"
)
def test_session_manager_raise(caplog):
    """Evaluates and determines whether the expected error in initialization is caught and handled correctly in error
    scenarios where the write directory doesn't exist and is required.

    The cached session manager factory should warn that the path doesn't yet exist when defining the options
    that initialize the CachedSessionManager.

    When creating a new session from the cached session manager, a SessionCreationError should be raised if
    the path still doesn't exist at this point.

    """

    mgr = sm.CachedSessionManager(
        user_agent="ua", cache_name="c", cache_directory=Path("/tmps"), backend="sqlite", raise_on_error=True
    )
    cache_path = Path(mgr.cache_path)
    assert (
        f"Warning: The parent directory, {cache_path.parent}, does not exist and need to be created before use."
        in caplog.text
    )

    with pytest.raises(SessionCreationError):
        _ = mgr()

    mgr = sm.CachedSessionManager(
        user_agent="ua", cache_name="c", cache_directory=Path("/tmps"), backend="sqlite", raise_on_error=False
    )
    session = mgr()
    assert isinstance(session, requests.Session)


def test_session_manager_backend_resolution(monkeypatch, caplog):
    """Evaluates whether the CachedSessionManager catches and raises the intended error on env resolution failure."""

    env_variable = "SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND"

    with monkeypatch.context() as m:
        m.setenv(env_variable, "REDIS")
        # Redis (case-insensitive) is a valid backend - so no error should be raised
        assert sm.CachedSessionManager(raise_on_error=True).backend == "redis"

        invalid_backend = "REDISSS"
        m.setenv(env_variable, invalid_backend)

        # the fallback should be validated before use and raise a warning if the env variable is invalid
        sqlite_session_fallback = sm.CachedSessionManager(raise_on_error=False)
        assert sqlite_session_fallback.backend == "sqlite"
        assert (
            f"A cached session backend cannot be created with the environment variable '{env_variable}'.: "
            "Defaulting to the `sqlite` backend instead..."
        ) in caplog.text

        # when errors are enabled, validation should occur normally
        with pytest.raises(SessionConfigurationError) as excinfo:
            _ = sm.CachedSessionManager(raise_on_error=True)
        assert f"Requests-Cache does not support a backend by the name of {invalid_backend.lower()}" in str(
            excinfo.value
        )

    # after the context the default backnd should be SQLite otherwise
    assert sm.CachedSessionManager(raise_on_error=True).backend == "sqlite"


def test_session_manager_cache_directory_creation_error(monkeypatch):
    """Evaluates whether the CachedSessionManager catches and raises the intended error on directory resolution failure.

    This method mocks the get_default_writable_directory directly to raise a permission error to directly determine how
    the `get_cache_directory` class method handles the failure.

    """

    err = "Directly Raised Error"
    monkeypatch.setattr(sm, "get_default_writable_directory", raise_error(PermissionError, err))
    with pytest.raises(SessionCacheDirectoryError) as excinfo:
        _ = sm.CachedSessionManager._default_cache_directory()

    assert f"Could not create cache directory due to an exception: {err}" in str(excinfo.value)


#
#   mgr = sm.CachedSessionManager(
#       user_agent="ua", cache_name="c", backend="sqlite", raise_on_error=False
#   )

#   session = mgr()
#   assert isinstance(session, requests.Session)


def test_path_edge_case():
    """Verifies whether the circumstance where a cache_name is preceded by a `./' indicating that the current directory
    is accounted for and ignored/removed when initializing the `CachedSessionManager`.

    Instantiation should not fail and the cache name will not contain the preceding `./`

    """
    cache_name = "./cache"
    cache_directory = Path("/tmp")
    cache_path = str(cache_directory / cache_name.replace("./", ""))
    mgr = sm.CachedSessionManager(cache_name=cache_name, cache_directory=cache_directory, backend="sqlite")
    assert mgr.cache_path == cache_path


def test_cache_missing_dep(caplog):
    """Verifies that the backend, when it doesn't exist, raises the appropriate error with a warning message."""
    backend = "sql light"

    with pytest.raises(SessionCreationError):
        _ = sm.CachedSessionManager(
            user_agent="ua", cache_name="c", cache_directory="/tmp", backend=backend  # type:ignore
        )

    assert "The specified backend is not supported by Requests-Cache:" in caplog.text


def test_cache_directory_string_coercion(tmp_path):
    """Verifies that string typed cache_directory attributes are transformed into Path objects during instantiation."""
    mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory=str(tmp_path), backend="sqlite")
    assert isinstance(mgr.cache_directory, Path)
    assert mgr.cache_directory == tmp_path


def test_cached_session_manager_properties(tmp_path):
    """Verifies that path object inputs used for cached session creation are identical after instantiation."""
    mgr = sm.CachedSessionManager(
        user_agent="ua", cache_name="c", cache_directory=tmp_path, backend="sqlite", expire_after=42
    )
    assert mgr.cache_directory == tmp_path
    assert mgr.expire_after == 42


def test_get_cache_directory_package_and_home(monkeypatch, tmp_path):
    """Tests directory behavior by simulating a scenario where the package directory is not writeable.

    In such cases, the directory used must fallback to home if it is writeable.

    """
    monkeypatch.setattr(sm.session_models, "__file__", str(tmp_path / "fake.py"))
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
    # Remove parent.exists() check by patching Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False)
    home = Path.home()
    result = sm.CachedSessionManager.get_cache_directory()
    assert str(home) in str(result)


def test_redis_session_manager_default_kwargs(caplog):
    """Verifies that default redis kwargs match `scholar_flux.data_storage.RedisStorage.DEFAULT_CONFIG`."""
    session_manager = sm.CachedSessionManager(backend="redis")
    assert session_manager.kwargs == RedisStorage.DEFAULT_CONFIG
    assert "Auto-configured Redis from RedisStorage.DEFAULT_CONFIG" in caplog.text


def test_mongodb_session_manager_default_kwargs(caplog):
    """Verifies that default mongodb kwargs match `scholar_flux.data_storage.MongoDBStorage.DEFAULT_CONFIG`."""
    session_manager = sm.CachedSessionManager(backend="mongodb")

    assert session_manager.kwargs == {k: v for k, v in MongoDBStorage.DEFAULT_CONFIG.items() if k in ("host", "port")}
    assert "Auto-configured MongoDB from MongoDBStorage.DEFAULT_CONFIG" in caplog.text


def test_get_cache_directory_package_with_env(monkeypatch, tmp_path):
    """Tests the behavior of the `SCHOLAR_FLUX_CACHE_DIRECTORY` environment variable when provided.

    This test verifies that cache directory specified in the environment variable will be used when set and confirmed as
    loaded within the package config.

    """
    env_var_name = "SCHOLAR_FLUX_CACHE_DIRECTORY"
    env_var_value = str(tmp_path)
    monkeypatch.setenv(env_var_name, env_var_value)
    config_settings.load_config(reload_os_env=True)

    result = sm.CachedSessionManager.get_cache_directory()
    assert result is not None and result == Path(tmp_path)
