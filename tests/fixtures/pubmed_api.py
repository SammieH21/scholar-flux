from scholar_flux.api import SearchAPI, SearchCoordinator
from requests.models import Response
import pytest
from pathlib import Path
import json
import re
from typing import Any


@pytest.fixture
def pubmed_search_api() -> SearchAPI:
    """Defines a basic PubMed SearchAPI to use when simulating the retrieval of responses using requests_mock"""
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
    """
    Defines a basic search API to use when simulating the retrieval, processing and caching of responses from
    the PubMed api using requests_mock.
    """
    coordinator = SearchCoordinator(search_api=pubmed_search_api)
    return coordinator


@pytest.fixture
def mock_pubmed_search_endpoint() -> re.Pattern:
    """Defines the pattern for the endpoint to query when creating an eSearch  requests using requests_mock"""
    mock_pubmed_search_endpoint = re.compile("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi.*")
    return mock_pubmed_search_endpoint


@pytest.fixture
def mock_pubmed_fetch_endpoint() -> re.Pattern:
    """Defines the pattern for the endpoint to query when creating an eFetch request using requests_mock"""
    mock_pubmed_fetch_endpoint = re.compile("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi.*")
    return mock_pubmed_fetch_endpoint


@pytest.fixture
def mock_pubmed_search_json_path() -> Path:
    """
    Defines the path where JSON data is stored too simulate the retrieval of page 3 eSearch data from the PubMed API.
    """
    mock_pubmed_search_json_path = Path(__file__).resolve().parent.parent / "mocks" / "mock_pubmed_search.json"
    return mock_pubmed_search_json_path


@pytest.fixture
def mock_pubmed_fetch_json_path() -> Path:
    """
    Defines the path where JSON data is stored too simulate the retrieval of page 3 eFetch data from the PubMed API.
    """
    mock_pubmed_fetch_json_path = Path(__file__).resolve().parent.parent / "mocks" / "mock_pubmed_fetch.json"
    return mock_pubmed_fetch_json_path


@pytest.fixture
def mock_pubmed_search_data(mock_pubmed_search_json_path) -> dict[str, Any]:
    """
    The data to return when simulating the retrieval of page 3 eSearch data from the PubMed API with the current
    query and requests_mock.
    """
    mock_pubmed_search_data = json.loads(mock_pubmed_search_json_path.read_text(encoding="utf-8"))
    return mock_pubmed_search_data


@pytest.fixture
def mock_pubmed_fetch_data(mock_pubmed_fetch_json_path) -> dict[str, Any]:
    """
    The data to return when simulating the retrieval of page 3 eFetch data from the PubMed API with the current
    query and requests_mock.
    """
    mock_pubmed_fetch_json_data = json.loads(mock_pubmed_fetch_json_path.read_text(encoding="utf-8"))
    return mock_pubmed_fetch_json_data


@pytest.fixture
def mock_pubmed_search_response(mock_pubmed_search_data) -> Response:
    """
    A fixture that uses the requests_mock package to simulate the retrieval of a requests.Response instance
    for page 3 of the PubMed eSearch API with the current query.
    """
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
    """
    A fixture that uses the requests_mock package to simulate the retrieval of a requests.Response instance
    for page 3 of the PubMed eFetch API with the current query.
    """
    # Create a mock object that behaves like a Response instance
    mock_response = Response()

    # Set desired attributes and method return values
    mock_response.status_code = 200
    mock_response._content = mock_pubmed_fetch_data["_content"].encode("utf-8")
    mock_response.headers.update({"Content-Type": "text/xml"})
    mock_response.encoding = "UTF-8"

    return mock_response


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
