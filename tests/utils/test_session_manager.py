import pytest
import requests
from unittest.mock import patch, MagicMock
from requests_cache import CachedSession
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

import scholar_flux.sessions.session_manager as sm
from scholar_flux.utils import config_settings
from scholar_flux.exceptions.util_exceptions import SessionCreationError

def test_session_manager_valid_user_agent():
    mgr = sm.SessionManager(user_agent="test-agent")
    session = mgr.configure_session()
    assert session.headers["User-Agent"] == "test-agent"
    assert "SessionManager(user_agent='test-agent')" in repr(mgr)

def test_session_manager_invalid_user_agent():
    with pytest.raises(SessionCreationError):
        sm.SessionManager(user_agent='')

def test_session_manager_no_user_agent():
    mgr = sm.SessionManager()
    session = mgr.configure_session()
    user_agent = session.headers.get('User-Agent','')
    user_agent = user_agent.decode() if isinstance(user_agent, bytes) else user_agent
    assert "User-Agent" in session.headers and 'python-requests' in user_agent.lower()

def test_cached_session_manager_valid():
    mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory=Path("/tmp"), backend="sqlite")
    session = mgr.configure_session()
    assert isinstance(session, CachedSession)
    assert mgr.cache_name == "c"
    assert mgr.backend == "sqlite"
    assert mgr.user_agent == "ua"
    assert "CachedSessionManager(config=" in repr(mgr)

        

@pytest.mark.parametrize("param_overrides", [{'user_agent':''}, # user_agent must be provided or None
                                             {'cache_name':None}, # cache name cannot be None, used by all caches
                                             {'cache_name':'a/nested/cache'}, # cache name cannot be None, used by all caches
                                             {'expire_after':-2}, # a negative expire_after (other than -1) should trigger a session creation error
                                             {"backend":'a-non existent backend'}, # requests_cache.CachedSession must receive a valid backend
                                             {"backend":None} # backend cannot be None
                                            ])
def test_session_manager_invalid(param_overrides):
    """
    Test potentially common configuration issues that should raise a SessionCreationError
    """
    with pytest.raises(SessionCreationError):
        # a negative expire_after value should raise a validation error which triggers the session creation error
        params=dict(user_agent="ua", cache_name="c", expire_after=20,cache_directory=Path("/tmp"), backend="sqlite") | param_overrides
        sm.CachedSessionManager(**params)


def test_session_manager_raise(caplog):
    """
    Evaluates and determines whether the expected error in initialization is caught and handled correctly in
    error scenarios where the write directory doesn't exist and is required
    """

    mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory=Path("/tmps"), backend='sqlite', raise_on_error = True)
    cache_path = Path(mgr.cache_path)
    assert f"Warning: The parent directory, {cache_path.parent}, does not exist and need to be created before use." in caplog.text

    with pytest.raises(SessionCreationError):
        session = mgr()

    mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory=Path("/tmps"), backend='sqlite', raise_on_error = False)
    session = mgr()
    assert isinstance(session,requests.Session)

def test_path_edge_case():
    cache_name='./cache'
    cache_directory=Path('/tmp')
    cache_path = str(cache_directory / cache_name.replace('./',''))
    mgr = sm.CachedSessionManager(cache_name=cache_name,cache_directory=cache_directory, backend='sqlite')
    assert mgr.cache_path == cache_path

def test_cache_missing_dep(caplog):
    backend='sql light'
    
    with pytest.raises(SessionCreationError):
        mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory='/tmp', backend=backend) # type:ignore

    assert "The specified backend is not supported by Requests-Cache:" in caplog.text

def test_cache_directory_string_coercion(tmp_path):
   mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory=str(tmp_path), backend="sqlite")
   assert isinstance(mgr.cache_directory, Path)
   assert mgr.cache_directory == tmp_path

def test_cached_session_manager_properties(tmp_path):
    # monkeypatch.setattr(sm.requests_cache, "CachedSession", lambda **kwargs: MagicMock())
    mgr = sm.CachedSessionManager(user_agent="ua", cache_name="c", cache_directory=tmp_path, backend="sqlite", expire_after=42)
    assert mgr.cache_directory == tmp_path
    assert mgr.expire_after == 42

def test_get_cache_directory_package_and_home(monkeypatch, tmp_path):
    # Simulate package directory not existing, fallback to home
    monkeypatch.setattr(sm.session_models, "__file__", str(tmp_path / "fake.py"))
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
    # Remove parent.exists() check by patching Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False)
    home = Path.home()
    result = sm.CachedSessionManager.get_cache_directory()
    assert str(home) in str(result)

def test_get_cache_directory_package_with_env(monkeypatch, tmp_path):
    # Simulate anenvironment variable for the cache directorybeing set and config settings reloaded
    env_var_name = "SCHOLAR_FLUX_CACHE_DIRECTORY"
    env_var_value = str(tmp_path)
    monkeypatch.setenv(env_var_name, env_var_value)
    config_settings.load_config(reload_os_env=True)

    result = sm.CachedSessionManager.get_cache_directory()
    assert result is not None and result == Path(tmp_path)
