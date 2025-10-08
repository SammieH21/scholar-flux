import pytest
import hashlib
from unittest.mock import Mock
from requests.models import Response
from http.client import responses
import json
from typing import Any
from pathlib import Path


@pytest.fixture
def mock_response() -> Response:
    """Create a mock response object."""
    response = Mock(spec=Response)
    response.url = "https://api.example.com/test"
    response.status_code = 200
    response.content = b"test content"
    response.status = responses[200]
    return response


@pytest.fixture
def mock_successful_response() -> Response:
    """Create a response object that simulates a 429 rate limit exceeded error"""
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.status = responses[200]  # type:ignore
    return mock_response


@pytest.fixture
def mock_internal_error_response() -> Response:
    """Create a response object that simulates a 500 internal error"""
    mock_response = Response()
    mock_response.status_code = 500
    mock_response.status = responses[500]  # type:ignore
    return mock_response


@pytest.fixture
def mock_unauthorized_response() -> Response:
    """Create a response object that simulates a 401 unauthorized error"""
    mock_response = Response()
    mock_response.status_code = 401
    mock_response.status = responses[401]  # type:ignore
    return mock_response


@pytest.fixture
def mock_rate_limit_exceeded_response() -> Response:
    """Create a response object that simulates a 429 rate limit exceeded error"""
    mock_response = Response()
    mock_response.status_code = 429
    mock_response.status = responses[429]  # type:ignore
    return mock_response


@pytest.fixture
def mock_cache_storage_data() -> dict[str, Any]:
    """Test data for cache operations."""
    return {
        "response_hash": hashlib.sha256(b"test content").hexdigest(),
        "status_code": 200,
        "raw_response": b"test content",
        "parsed_response": {"key": "value"},
        "processed_records": {"processed": True},
        "metadata": {"source": "test"},
    }


@pytest.fixture
def mock_academic_json_path() -> Path:
    mock_academic_json_path = Path(__file__).resolve().parent.parent / "mocks" / "mock_article_response.json"
    return mock_academic_json_path


@pytest.fixture
def mock_academic_json(mock_academic_json_path) -> dict:
    mock_academic_json = json.loads(mock_academic_json_path.read_text(encoding="utf-8"))
    return mock_academic_json


@pytest.fixture
def academic_json_response(mock_academic_json) -> Response:

    # Create a mock object that behaves like a Response instance
    mock_response = Response()

    # Set desired attributes and method return values
    mock_response.status_code = 200
    # mock_response.text = str(mock_academic_json)
    mock_response.raw = mock_response.text
    mock_response._content = json.dumps(mock_academic_json).encode("utf-8")
    mock_response.headers.update({"Content-Type": "application/json"})
    mock_response.encoding = "utf-8"

    return mock_response


@pytest.fixture
def mock_academic_yaml_path() -> Path:
    mock_academic_yaml_path = Path(__file__).resolve().parent.parent / "mocks" / "mock_article_response.yaml"
    return mock_academic_yaml_path


@pytest.fixture
def mock_academic_yaml(mock_academic_yaml_path) -> str:
    mock_academic_yaml = mock_academic_yaml_path.read_text(encoding="utf-8")
    return mock_academic_yaml


@pytest.fixture
def academic_yaml_response(mock_academic_yaml) -> Response:

    # Create a mock object that behaves like a Response instance
    mock_response = Response()

    # Set desired attributes and method return values
    mock_response.status_code = 200
    # mock_response.text = str(mock_academic_yaml)
    mock_response.raw = mock_response.text
    mock_response._content = mock_academic_yaml
    mock_response.headers.update({"Content-Type": "application/yaml"})
    mock_response.encoding = "utf-8"

    return mock_response


__all__ = [
    "mock_response",
    "mock_cache_storage_data",
    "mock_successful_response",
    "mock_internal_error_response",
    "mock_unauthorized_response",
    "mock_rate_limit_exceeded_response",
    "mock_academic_json_path",
    "mock_academic_json",
    "academic_json_response",
    "mock_academic_yaml_path",
    "mock_academic_yaml",
    "academic_yaml_response",
]
