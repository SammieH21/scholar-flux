from scholar_flux.api import SearchCoordinator, SearchAPI
from scholar_flux.utils import FileUtils
import pytest
from pathlib import Path


@pytest.fixture
def plos_search_api() -> SearchAPI:
    plos_search_api = SearchAPI.from_defaults(
        query="social wealth equity", provider_name="plos", records_per_page=100, user_agent="SammieH"
    )
    return plos_search_api


@pytest.fixture
def plos_coordinator(plos_search_api):
    coordinator = SearchCoordinator(search_api=plos_search_api)
    return coordinator


@pytest.fixture
def plos_page_1_url(plos_search_api):
    params = plos_search_api.build_parameters(page=1)
    request = plos_search_api.prepare_request(plos_search_api.base_url, parameters=params)
    return request.url


@pytest.fixture
def plos_page_1_data() -> list | dict:
    json_path = Path(__file__).parent.parent / "mocks/plos_page_1_data.json"
    plos_page_1_data = FileUtils.load_data(json_path)
    assert isinstance(plos_page_1_data, (list, dict))
    return plos_page_1_data


@pytest.fixture
def plos_page_2_url(plos_search_api):
    params = plos_search_api.build_parameters(page=2)
    request = plos_search_api.prepare_request(plos_search_api.base_url, parameters=params)
    return request.url


@pytest.fixture
def plos_page_2_data() -> list | dict:
    json_path = Path(__file__).parent.parent / "mocks/plos_page_2_data.json"
    plos_page_2_data = FileUtils.load_data(json_path)
    assert isinstance(plos_page_2_data, (list, dict))
    return plos_page_2_data


@pytest.fixture
def plos_headers() -> dict:
    plos_content_type = {"Content-Type": "application/json charset=UTF-8"}
    return plos_content_type


__all__ = [
    "plos_search_api",
    "plos_coordinator",
    "plos_page_1_url",
    "plos_page_1_data",
    "plos_page_2_url",
    "plos_page_2_data",
    "plos_headers",
]
