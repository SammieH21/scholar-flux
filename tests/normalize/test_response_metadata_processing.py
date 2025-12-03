from scholar_flux.api import (
    APIResponse,
    ProcessedResponse,
    ErrorResponse,
    NonResponse,
    ProviderConfig,
    provider_registry,
    SearchCoordinator,
    ReconstructedResponse,
)
from scholar_flux.utils import get_nested_data, coerce_int
from scholar_flux.api.models import ResponseMetadataMap, SearchResult
import pytest
from typing import Callable, Generator, Any
from functools import partial
from tests.testing_utilities import search_coordinator_mocking_context


@pytest.fixture
def mock_metadata_map():
    """Fixture providing a mocked metadata map with nested field paths for testing metadata processing."""
    mock_metadata_map = ResponseMetadataMap(records_per_page="pageSize", total_query_hits="statistics.numResults")
    return mock_metadata_map


@pytest.fixture
def mock_flattened_metadata_map():
    """Fixture providing a mocked metadata map with nested field paths for testing metadata processing."""
    mock_metadata_map = ResponseMetadataMap(records_per_page="pageSize", total_query_hits="numResults")
    return mock_metadata_map


@pytest.fixture
def mock_provider_config(basic_parameter_config, mock_flattened_metadata_map) -> ProviderConfig:
    """Fixture used to test the normalization of response metadata."""
    mock_provider_config = ProviderConfig(
        provider_name="mock_api_provider",
        base_url="https://mock-academic-provider.edu",
        parameter_map=basic_parameter_config.map,
        records_per_page=3,
        request_delay=0.01,
        metadata_map=mock_flattened_metadata_map,
    )
    return mock_provider_config


@pytest.fixture
def with_mock_api_provider(mock_provider_config):
    """Temporarily adds a new provider to the registry during testing."""
    provider_registry.add(mock_provider_config)
    yield
    provider_registry.remove(mock_provider_config.provider_name)


@pytest.fixture
def mock_metadata_dictionary():
    """Fixture used to test the extraction and processing of `total_query_hits` and `records_per_page`."""
    return {"pageSize": "10", "statistics": {"numResults": "50"}, "startPage": "1"}


def test_normalization_not_implemented():
    """Verifies that classes without a subclassed `normalize` method raise an error by default."""
    api_response = APIResponse()
    with pytest.raises(NotImplementedError) as excinfo:
        _ = api_response.normalize()
    assert (f"Normalization is not implemented for responses of type, {api_response.__class__.__name__}") in str(
        excinfo.value
    )


@pytest.mark.parametrize("ResponseType", (ErrorResponse, NonResponse))
def test_error_response_return_nonetype(ResponseType):
    """Verifies that ErrorResponse/NonResponse `normalize()` returns None."""
    response = ResponseType(message="Test error", error="TestException")

    # normalized_records should still remain a static property (always None)
    assert response.process_metadata() is None
    assert response.processed_metadata is None


def test_responose_metadata_processing_method_equality(mock_metadata_map, mock_metadata_dictionary):
    """Verifies that `ProcessedResponse.process_metadata` and `ResponseMetadataMap()` produces equal results."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response, metadata=mock_metadata_dictionary)

    processed_metadata = response.process_metadata(mock_metadata_map)
    assert mock_metadata_map(mock_metadata_dictionary) == processed_metadata
    assert response.processed_metadata == {
        key: coerce_int(get_nested_data(mock_metadata_dictionary, value))
        for key, value in mock_metadata_map.model_dump().items()
    }


def test_mock_metadata_map_response_nonexistent_keys():
    """Tests several edge-cases (empty lists/strings/non-existent keys) that should return `None` on processing."""
    data: dict[str, Any] = {"hits": "230", "page": "1"}

    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response, metadata=data)

    map1 = ResponseMetadataMap(total_query_hits="")
    map3 = ResponseMetadataMap(total_query_hits="nested.non-existent.element")

    # each of the following should return a dictionary with identical, empty normalization fields
    processed_response1 = response.process_metadata(map1)
    processed_response3 = response.process_metadata(map3, update_metadata=True)
    assert processed_response1 == processed_response3
    assert processed_response1 and processed_response1["total_query_hits"] is None


def test_processing_without_records_update(mock_metadata_map, mock_metadata_dictionary):
    """Tests if processing with `update_metadata=false` flag will not update `.processed_metadata`."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response, metadata=mock_metadata_dictionary)
    assert response.process_metadata(mock_metadata_map, update_metadata=False) and response.processed_metadata is None


def test_missing_metadata():
    """Tests whether processing `ProcessedResponse.metadata` will instead return None when missing a metadata dict."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response)

    assert response.process_metadata(metadata_map=ResponseMetadataMap()) is None


def test_missing_response_search_result(caplog):
    """Tests whether processing search result metadata will return None if a response isn't provided."""
    search_result = SearchResult(page=1, query="new-query", provider_name="mock-provider")
    metadata = search_result.process_metadata()
    assert metadata is None


@pytest.fixture
def response_json(mock_metadata_dictionary: dict) -> dict:
    """A basic JSON data set that enables the processing testing for JSON records data after response retrieval."""
    response_json = {"records": [], **mock_metadata_dictionary}
    return response_json


@pytest.fixture
def default_search_coordinator(with_mock_api_provider: None) -> Generator[SearchCoordinator, None, None]:
    """A basic search coordinator that uses a temporary provider for testing common metadata processing scenarios."""
    provider_name = "mock_api_provider"
    coordinator = SearchCoordinator(query="test-query", provider_name=provider_name)
    yield coordinator


@pytest.fixture
def setup_mocking(default_search_coordinator: SearchCoordinator, response_json: dict) -> Callable:
    """Creates a nested function used to mock search results using a coordinator, response JSON, and requests_mock."""
    partial_mocking_context = partial(
        search_coordinator_mocking_context,
        search_coordinator=default_search_coordinator,
        json_data=response_json,
        headers={"content-type": "application/json"},
    )

    return partial_mocking_context


def test_search_processing(default_search_coordinator, setup_mocking):
    """Verifies that the processing of records occurs as intended through the full, orchestrated pipeline."""
    with setup_mocking(page=1) as _:
        response = default_search_coordinator.search(page=1)
        search_result_list = default_search_coordinator.search_pages(pages=[1])

    search_result = search_result_list[0]

    # will use the URL to resolve the response to the provider's field map
    processed_metadata = response.process_metadata()
    processed_metadata_two = search_result.process_metadata(update_metadata=False)
    processed_metadata_three = search_result_list.process_metadata(update_metadata=False, include={})

    assert processed_metadata and isinstance(processed_metadata, dict)

    # the processing with a ProcessedResponse/SearchResult/SearchResultList shouldn't affect the final result
    assert processed_metadata == processed_metadata_two
    assert processed_metadata == processed_metadata_three[0]


def test_search_processing_structure(default_search_coordinator, setup_mocking):
    """Verifies that the processing of records returns a list of dictionaries with the required structure."""
    provider_config = provider_registry[default_search_coordinator.api.provider_name]
    assert provider_config and provider_config.metadata_map

    with setup_mocking(page=1) as _:
        response = default_search_coordinator.search(page=1)

    assert response.process_metadata() == response.processed_metadata

    fields = ResponseMetadataMap.model_fields.keys()
    assert all(field in response.processed_metadata for field in fields)
    assert all(value is not None for value in response.processed_metadata.values())

    # all normalized record fields should be present in each record
    metadata_map = provider_config.metadata_map
    assert metadata_map
