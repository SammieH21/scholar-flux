import pytest
from unittest.mock import MagicMock
import requests

from scholar_flux.api import BaseAPI
from scholar_flux.exceptions import RequestCreationException, SessionCreationError

def test_configure_session_creates_new_session():
    api = BaseAPI(user_agent="test-agent")
    assert isinstance(api.session, requests.Session)
    assert api.user_agent == "test-agent"

def test_configure_session_error():
    with pytest.raises(SessionCreationError):
        # The API needs a user agent for user identification
        _ = BaseAPI(user_agent='')


def test_user_agent_property_setter_and_getter():
    api = BaseAPI()
    api.user_agent = "custom-agent"
    assert api.user_agent == "custom-agent"
    assert api.session.headers['User-Agent'] == "custom-agent"

def test_prepare_request_url_and_params():
    api = BaseAPI()
    req = api.prepare_request("https://api.example.com", "endpoint", {"foo": "bar", 'api_key':"123"})
    assert isinstance(req.url, str) and req.url.startswith("https://api.example.com/endpoint")
    assert "foo=bar" in req.url
    assert "api_key=123" in req.url


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
    monkeypatch.setattr(api.session, "send", lambda req, timeout=10: (_ for _ in ()).throw(requests.RequestException("fail")))
    api.prepare_request("https://api.example.com", "endpoint")
    with pytest.raises(requests.RequestException):
        # this should throw an error based on the patched exception
        api.send_request("https://api.example.com", "endpoint")

