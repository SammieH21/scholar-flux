from scholar_flux.api import SearchAPI, SearchCoordinator
from requests.models import Response
import pytest
from pathlib import Path
import json
import re
from typing import Any


@pytest.fixture
def pubmed_search_api() -> SearchAPI:
    pubmed_search_api = SearchAPI.from_defaults(
        query="mental health",
        provider_name="pubmed",
        api_key="this_is_a_mock_api_key",
        records_per_page=100,
        user_agent="scholar_flux",
    )
    return pubmed_search_api


@pytest.fixture
def pubmed_coordinator(pubmed_search_api) -> SearchCoordinator:
    coordinator = SearchCoordinator(search_api=pubmed_search_api)
    return coordinator


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


# def mock_pubmed_fetch_xml_response(mock_pubmed_search_data, mock_pubmed_fetch_data):

#   pubmed_api_key = "this_is_a_mocked_api_key"
#   with requests_mock.Mocker() as m:
#       m.get(
#           mock_pubmed_fetch_endpoint,
#           content=mock_pubmed_search_data["_content"].encode(),
#           headers={"Content-Type": "text/xml; charset=UTF-8"},
#           status_code=200,
#       )
#       return coordinator.fetch(page = 1)

__all__ = [
    "mock_pubmed_search_json_path",
    "mock_pubmed_fetch_json_path",
    "mock_pubmed_search_data",
    "mock_pubmed_fetch_data",
    "mock_pubmed_search_endpoint",
    "mock_pubmed_fetch_endpoint",
    "mock_pubmed_search_response",
    "mock_pubmed_fetch_response",
]
