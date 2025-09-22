import pytest
import re
from unittest.mock import MagicMock
import requests

from scholar_flux.api import BaseAPI
from scholar_flux.exceptions import RequestCreationException, SessionCreationError, APIParameterException
from scholar_flux.sessions import SessionManager, CachedSessionManager
from requests_cache import CachedSession


def test_configure_session_creates_new_session(caplog):
    api = BaseAPI(user_agent="test-agent")
    assert isinstance(api.session, requests.Session)
    assert api.user_agent == "test-agent"
    assert "Creating a regular session for the BaseAPI..." in caplog.text


def test_configure_session_error():
    with pytest.raises(SessionCreationError):
        # The API needs a user agent for user identification
        _ = BaseAPI(user_agent="")


def test_user_agent_property_setter_and_getter():
    user_agent = "custom-agent"
    api = BaseAPI()
    api.user_agent = user_agent
    assert api.user_agent == user_agent
    assert api.session.headers["User-Agent"] == user_agent

    api.user_agent = user_agent.encode()  # type: ignore
    assert api.session.headers["User-Agent"] == user_agent  # decoded before setting
    assert api.user_agent == user_agent  # decoded on setting and retrieval for consistencyy


def test_invalid_session(caplog):
    session = "an invalid session"
    with pytest.raises(SessionCreationError) as excinfo:
        _ = BaseAPI(session=session)  # type: ignore

    assert "An unexpected error occurred during session initialization." in caplog.text
    assert f"Expected a requests.Session, a session subclass, or CachedSession, received {type(session)}" in str(
        excinfo.value
    )


def test_default_session_override(caplog):
    session_manager = CachedSessionManager(user_agent="base_api_tester", backend="memory")
    session = session_manager()
    assert isinstance(session, CachedSession)
    api = BaseAPI(session=session, use_cache=False)
    assert isinstance(api.session, requests.Session)
    assert "Removing session caching for the BaseAPI..." in caplog.text


def test_cached_session_override(caplog):
    session_manager = SessionManager(user_agent="base_api_tester")
    session = session_manager()
    assert isinstance(session, requests.Session)
    api = BaseAPI(session=session, use_cache=True)
    assert isinstance(api.session, CachedSession)
    assert "Creating a cached session for the BaseAPI..." in caplog.text

    original_setting = BaseAPI.DEFAULT_USE_CACHE
    BaseAPI.DEFAULT_USE_CACHE = True
    api = BaseAPI()
    assert isinstance(api.session, CachedSession)
    BaseAPI.DEFAULT_USE_CACHE = original_setting


def test_prepare_request_url_and_params():
    api = BaseAPI()
    req = api.prepare_request("https://api.example.com", "endpoint", {"foo": "bar", "api_key": "123"})
    assert isinstance(req.url, str) and req.url.startswith("https://api.example.com/endpoint")
    assert "foo=bar" in req.url
    assert "api_key=123" in req.url


def test_validate_parameters(caplog):
    api = BaseAPI()
    parameters = "not a dictionary"
    with pytest.raises(APIParameterException) as excinfo:
        _ = api._validate_parameters(parameters)  # type: ignore

    assert f"Expected the parameter overrides to be a dictionary, received type {type(parameters)}" in str(
        excinfo.value
    )

    parameter_dict = {"a_valid_parameter": 2, "another_valid_parameter_key": 1, 0: "not a valid key"}
    with pytest.raises(APIParameterException) as excinfo:
        _ = api._validate_parameters(parameter_dict)  # type: ignore

    assert f"Expected all parameter names to be strings. verify the types for each key: {parameter_dict.keys()}" in str(
        excinfo.value
    )

    del parameter_dict[0]

    # passes through without modification after successful validation
    assert BaseAPI._validate_parameters(parameter_dict) == parameter_dict  # type: ignore


def test_prepare_request_exception(monkeypatch):
    api = BaseAPI()
    monkeypatch.setattr(requests, "Request", lambda *a, **kw: (_ for _ in ()).throw(Exception("fail")))
    with pytest.raises(RequestCreationException):
        api.prepare_request("https://api.example.com", "endpoint")


def test_send_request_success(monkeypatch):
    api = BaseAPI()
    mock_response = MagicMock(spec=requests.Response)
    monkeypatch.setattr(api.session, "send", lambda req, timeout=10: mock_response)
    response = api.send_request("https://api.example.com", "endpoint")
    assert response is mock_response


def test_send_request_exception(monkeypatch):
    api = BaseAPI()
    monkeypatch.setattr(
        api.session, "send", lambda req, timeout=10: (_ for _ in ()).throw(requests.RequestException("fail"))
    )
    api.prepare_request("https://api.example.com", "endpoint")
    with pytest.raises(requests.RequestException):
        # this should throw an error based on the patched exception
        api.send_request("https://api.example.com", "endpoint")


@pytest.mark.parametrize(["use_cache"], [(True,), (False,)])
def test_representation(use_cache):
    api = BaseAPI(use_cache=use_cache)
    class_name = api.__class__.__name__
    api_string = rf"^{class_name}\(session=.*?{type(api.session).__name__}.*timeout={api.timeout}\)$"
    assert re.search(api_string, repr(api)) is not None
