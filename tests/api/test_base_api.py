import pytest
import re
import requests

from scholar_flux.api import BaseAPI
from scholar_flux.exceptions import RequestCreationException, SessionCreationError, APIParameterException
from scholar_flux.sessions import SessionManager, CachedSessionManager
from urllib.parse import urljoin
from requests_cache import CachedSession
import requests_mock


def test_configure_session_creates_new_session(caplog):
    """Test the creation of a new session object without direct specification"""
    api = BaseAPI(user_agent="test-agent")
    assert isinstance(api.session, requests.Session)
    assert api.user_agent == "test-agent"
    assert "Creating a regular session for the BaseAPI..." in caplog.text


def test_configure_session_error():
    """Ensure that excluding a user-agent results in an error being raised"""
    with pytest.raises(SessionCreationError):
        # The API needs a user agent for user identification
        _ = BaseAPI(user_agent="")


def test_user_agent_property_setter_and_getter():
    """Ensure that the user agent is handled in a consistent way, not depending on its type"""
    user_agent = "custom-agent"
    api = BaseAPI()
    api.user_agent = user_agent
    assert api.user_agent == user_agent
    assert api.session.headers["User-Agent"] == user_agent

    api.user_agent = user_agent.encode()  # type: ignore
    assert api.session.headers["User-Agent"] == user_agent  # decoded before setting
    assert api.user_agent == user_agent  # decoded on setting and retrieval for consistencyy


def test_invalid_session(caplog):
    """Verify that an invalid type raises an error as intended"""
    session = "an invalid session"
    with pytest.raises(SessionCreationError) as excinfo:
        _ = BaseAPI(session=session)  # type: ignore

    assert "An unexpected error occurred during session initialization." in caplog.text
    assert f"Expected a requests.Session, a session subclass, or CachedSession, received {type(session)}" in str(
        excinfo.value
    )


def test_default_session_override(caplog):
    """Ensure that directly specifying whether to cache or not modifies the session that is used"""
    session_manager = CachedSessionManager(user_agent="base_api_tester", backend="memory")
    session = session_manager()
    assert isinstance(session, CachedSession)
    api = BaseAPI(session=session, use_cache=False)
    assert isinstance(api.session, requests.Session)
    assert "Removing session caching for the BaseAPI..." in caplog.text


def test_cached_session_override(caplog):
    """Ensure, that if caching is directly specified, that a cached session is created if not already specified"""
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
    """Ensure that `prepare_request` operates in a consistent manner when formatting request parameters"""
    api = BaseAPI()
    req = api.prepare_request("https://api.example.com", "endpoint", {"foo": "bar", "api_key": "123"})
    assert isinstance(req.url, str) and req.url.startswith("https://api.example.com/endpoint")
    assert "foo=bar" in req.url
    assert "api_key=123" in req.url


def test_validate_parameters(caplog):
    """
    Ensure that parameter validation occurs as intended. When preparing a request, the _validate_parameters
    class method will expect a dictionary with keys as strings: integers are not valid keys and errors should
    be thrown in such cases.
    """
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

    # ensure that a dictionary without any parameters also passes the check
    assert BaseAPI._validate_parameters({}) == {}


def test_prepare_request_exception(monkeypatch):
    """Monkey patch an exception to ensure that, when preparing a request, it is caught as a RequestCreationException"""
    api = BaseAPI()
    monkeypatch.setattr(requests, "Request", lambda *a, **kw: (_ for _ in ()).throw(Exception("fail")))
    with pytest.raises(RequestCreationException):
        api.prepare_request("https://api.example.com", "endpoint")


def test_send_request_success():
    """
    Use request.mock to ensure that the process of both preparing and sending a request
    occurs as intended and is received as a requests.Response when using a requests backend
    """
    api = BaseAPI()

    base_url, endpoint = "https://api.example.com", "endpoint"
    content = b"test success"
    url = urljoin(base_url, endpoint)
    with requests_mock.Mocker() as m:
        m.get(
            url,
            status_code=200,
            content=content,
        )

        response = api.send_request(base_url, endpoint)

    assert response and isinstance(response, requests.Response)
    assert response.status_code == 200 and response.content == content


def test_send_request_exception(monkeypatch):
    """
    Ensure that the original exception is caught as is and raised when both preparing and sending a bad request
    that results in an exception
    """
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
    """Test cached and uncached representations of the BaseAPI to ensure consistency in representation in the cli"""
    api = BaseAPI(use_cache=use_cache)
    class_name = api.__class__.__name__
    api_string = rf"^{class_name}\(session=.*?{type(api.session).__name__}.*timeout={api.timeout}\)$"
    assert re.search(api_string, repr(api)) is not None


def test_api_summary():
    """A summary method is provided in addition to indicate how the object should appear in cli representations"""
    api = BaseAPI()
    representation = api.summary()

    assert re.search(r"^BaseAPI\(.*\)$", representation, re.DOTALL)
    assert re.search(f"session=.*{api.session.__class__.__name__}", representation)
    assert f"timeout={api.timeout}" in representation
