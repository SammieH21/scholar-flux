import pytest
import hashlib
from unittest.mock import Mock
from requests.models import Response
import json
import re
from pathlib import Path
from typing import Any


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    response = Mock(spec=Response)
    response.url = "https://api.example.com/test"
    response.status_code = 200
    response.content = b"test content"
    return response


@pytest.fixture
def mock_successful_response():
    """Create a response object that simulates a 429 rate limit exceeded error"""
    mock_response = Response()
    mock_response.status_code = 200
    return mock_response


@pytest.fixture
def mock_internal_error_response():
    """Create a response object that simulates a 500 internal error"""
    mock_response = Response()
    mock_response.status_code = 500
    return mock_response


@pytest.fixture
def mock_unauthorized_response():
    """Create a response object that simulates a 401 unauthorized error"""
    mock_response = Response()
    mock_response.status_code = 401
    return mock_response


@pytest.fixture
def mock_rate_limit_exceeded_response():
    """Create a response object that simulates a 429 rate limit exceeded error"""
    mock_response = Response()
    mock_response.status_code = 429
    return mock_response


@pytest.fixture
def mock_cache_storage_data():
    """Test data for cache operations."""
    return {
        "response_hash": hashlib.sha256(b"test content").hexdigest(),
        "status_code": 200,
        "raw_response": b"test content",
        "parsed_response": {"key": "value"},
        "processed_response": {"processed": True},
        "metadata": {"source": "test"},
    }


@pytest.fixture
def mock_academic_json_path() -> Path:
    mock_academic_json_path = Path(__file__).resolve().parent.parent / "mocks" / "mock_article_response.json"
    return mock_academic_json_path


@pytest.fixture
def mock_pubmed_search_endpoint() -> re.Pattern:
    mock_pubmed_search_endpoint = re.compile("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi.*")
    return mock_pubmed_search_endpoint


@pytest.fixture
def mock_pubmed_fetch_endpoint() -> re.Pattern:
    mock_pubmed_fetch_endpoint = re.compile("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi.*")
    return mock_pubmed_fetch_endpoint


@pytest.fixture
def mock_pubmed_search_json_path() -> Path:
    mock_pubmed_search_json_path = Path(__file__).resolve().parent.parent / "mocks" / "mock_pubmed_search.json"
    return mock_pubmed_search_json_path


@pytest.fixture
def mock_pubmed_fetch_json_path() -> Path:
    mock_pubmed_fetch_json_path = Path(__file__).resolve().parent.parent / "mocks" / "mock_pubmed_fetch.json"
    return mock_pubmed_fetch_json_path


@pytest.fixture
def mock_academic_json(mock_academic_json_path) -> dict:
    mock_academic_json = json.loads(mock_academic_json_path.read_text(encoding="utf-8"))
    return mock_academic_json


@pytest.fixture
def mock_pubmed_search_data(mock_pubmed_search_json_path) -> dict[str, Any]:
    mock_pubmed_search_data = json.loads(mock_pubmed_search_json_path.read_text(encoding="utf-8"))
    return mock_pubmed_search_data


@pytest.fixture
def mock_pubmed_fetch_data(mock_pubmed_fetch_json_path) -> dict[str, Any]:
    mock_pubmed_fetch_json_data = json.loads(mock_pubmed_fetch_json_path.read_text(encoding="utf-8"))
    return mock_pubmed_fetch_json_data


@pytest.fixture
def mock_pubmed_search_response(mock_pubmed_search_data) -> Response:

    # Create a mock object that behaves like a Response instance
    mock_response = Response()

    # Set desired attributes and method return values
    mock_response.status_code = 200
    mock_response._content = mock_pubmed_search_data["_content"].encode("utf-8")
    mock_response.headers.update({"Content-Type": "text/xml"})
    mock_response.encoding = "UTF-8"

    return mock_response


@pytest.fixture
def mock_pubmed_fetch_response(mock_pubmed_fetch_data) -> Response:

    # Create a mock object that behaves like a Response instance
    mock_response = Response()

    # Set desired attributes and method return values
    mock_response.status_code = 200
    mock_response._content = mock_pubmed_fetch_data["_content"].encode("utf-8")
    mock_response.headers.update({"Content-Type": "text/xml"})
    mock_response.encoding = "UTF-8"

    return mock_response


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
def mock_academic_json_response(mock_academic_json) -> Response:

    # Create a mock object that behaves like a Response instance
    mock_response = Mock(spec=Response)

    # Set desired attributes and method return values
    mock_response.status_code = 200
    mock_response.text = str(mock_academic_json)
    mock_response.raw = mock_response.text
    mock_response.content = mock_response.text.encode("utf-8")
    mock_response.json.return_value = mock_academic_json
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.raise_for_status = lambda: 200

    return mock_response


__all__ = [
    "mock_response",
    "mock_cache_storage_data",
    "mock_academic_json_path",
    "mock_pubmed_search_json_path",
    "mock_pubmed_fetch_json_path",
    "mock_academic_json",
    "mock_successful_response",
    "mock_internal_error_response",
    "mock_unauthorized_response",
    "mock_rate_limit_exceeded_response",
    "mock_academic_json_response",
    "academic_json_response",
    "mock_pubmed_search_data",
    "mock_pubmed_fetch_data",
    "mock_pubmed_search_endpoint",
    "mock_pubmed_fetch_endpoint",
    "mock_pubmed_search_response",
    "mock_pubmed_fetch_response",
]
