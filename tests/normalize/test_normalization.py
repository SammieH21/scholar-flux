from scholar_flux.api.normalization import AcademicFieldMap
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
from scholar_flux.api.models import SearchResult, SearchResultList
from scholar_flux.data import RecursiveDataProcessor
from scholar_flux.exceptions import RecordNormalizationException
from contextlib import contextmanager
import pytest
import requests_mock
from typing import Callable, Generator


@pytest.fixture
def mock_field_map():
    """Fixture used to test the normalization of a mocked json record."""
    mock_api_field_map = AcademicFieldMap(
        provider_name="mock_academic_provider",
        # Core identifiers - direct and nested field access
        record_id="work_id",
        doi="doi_url",
        url="work_id",  # Using work_id as URL fallback
        # Bibliographic metadata
        title="paper_title",
        abstract="summary",
        authors="author_list.name",  # Will need processing for nested list
        # Publication metadata - nested fields using dot notation
        journal="publication_info.journal_name",
        publisher="publication_info.publisher_name",
        year="publication_info.year_published",
        date_published="publication_info.publication_date",
        date_created="publication_info.date_created",
        # Content and classification - nested fields
        keywords="content_metadata.keywords",
        subjects="content_metadata.subjects",
        full_text="content_metadata.full_text_available",
        # Metrics and impact
        citation_count="metrics.citation_count",
        # Access and rights - nested fields
        open_access="access_info.is_open_access",
        license="access_info.license_type",
        # Document metadata
        record_type="document_info.type",
        language="document_info.language",
    )
    return mock_api_field_map


@pytest.fixture
def mock_provider_config(basic_parameter_config, mock_field_map) -> ProviderConfig:
    """Fixture used to test the normalization of academic response records."""
    mock_provider_config = ProviderConfig(
        provider_name="mock_academic_provider",
        base_url="https://mock-academic-provider.edu",
        parameter_map=basic_parameter_config.map,
        records_per_page=3,
        request_delay=0.01,
        field_map=mock_field_map,
    )
    return mock_provider_config


@pytest.fixture
def with_mock_academic_provider(mock_provider_config):
    """Temporarily adds a new provider to the registry during testing."""
    provider_registry.add(mock_provider_config)
    yield
    provider_registry.remove(mock_provider_config.provider_name)


@pytest.mark.parametrize("ResponseType", (APIResponse, ErrorResponse, NonResponse))
def test_normalization_not_implemented(ResponseType):
    """Verifies that classes without a subclassed `normalize` method"""
    api_response = ResponseType()
    with pytest.raises(NotImplementedError) as excinfo:
        _ = api_response.normalize()
    assert (f"Normalization is not implemented for responses of type, {api_response.__class__.__name__}") in str(
        excinfo.value
    )


def test_normalization_extracted_processed_equality(mock_field_map, mock_complex_json_records):
    """Tests whether normalizing a `ProcessedResponse` will fail gracefully with `raise_on_error=False`."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response, processed_records=mock_complex_json_records)
    response_two = ProcessedResponse(response=mock_response, extracted_records=mock_complex_json_records)

    assert response.normalize(mock_field_map) == response_two.normalize(mock_field_map)
    assert len(response.normalized_records or []) == len(mock_complex_json_records)


def test_normalization_without_records_update(mock_field_map, mock_complex_json_records):
    """Tests if normalization with `update_records=false` flag will not update `.normalized_records()`."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response, processed_records=mock_complex_json_records)
    assert response.normalize(mock_field_map, update_records=False) and response.normalized_records is None


def test_normalization_with_records_update(mock_field_map, mock_complex_json_records):
    """Tests whether the `update_records` affects whether `ProcessedResponse` updates `normalized_records` when needed."""
    updated_academic_field_map = AcademicFieldMap(provider_name="test_provider_two")
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response, processed_records=mock_complex_json_records)
    # the first normalized_records call will update
    assert response.normalize(mock_field_map, update_records=None) == response.normalized_records

    # the second normalized_records call will not update_records with `update=None` (already cached)
    updated_normalized_records = response.normalize(updated_academic_field_map, update_records=None)
    assert updated_normalized_records and updated_normalized_records != response.normalized_records
    # update_records=True forces the update
    assert response.normalize(updated_academic_field_map, update_records=True) is response.normalized_records
    assert response.normalized_records == updated_normalized_records


def test_missing_response_no_error(caplog):
    """Tests whether normalizing a `ProcessedResponse` will fail gracefully with `raise_on_error=False`."""
    response = ProcessedResponse()
    warning_message = "Returning an empty list."

    assert response.normalize(raise_on_error=False) == []
    assert warning_message in caplog.text


def test_missing_records():
    """Tests whether normalizing a `ProcessedResponse` will fail gracefully with `raise_on_error=False`."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(response=mock_response)

    assert response.normalize(field_map=AcademicFieldMap(), raise_on_error=True) == []


def test_missing_response_search_result(caplog):
    """Tests whether normalizing a search result will raise an error if a response isn't provided."""
    search_result = SearchResult(page=1, query="new-query", provider_name="mock-provider")
    with pytest.raises(RecordNormalizationException) as excinfo:
        _ = search_result.normalize(raise_on_error=True)
    assert "Cannot normalize a response result of type `None`." in str(excinfo.value)


def test_search_result_normalization_with_unknown_provider(mock_complex_json_records, caplog):
    """Verifies whether normalizing a search_result without a provider raises an error and/or fails gracefully."""
    mock_response = ReconstructedResponse.build(
        status_code=200, url="https://non-existent-url.com", json=mock_complex_json_records
    )

    processed_response = ProcessedResponse(
        response=mock_response, extracted_records=mock_complex_json_records, processed_records=mock_complex_json_records
    )

    search_result = SearchResult(
        query="test-query", page=1, provider_name="non_existent_provider", response_result=processed_response
    )

    search_result_list = SearchResultList([search_result])

    e = f"The URL, {processed_response.url}, does not resolve to a known provider in the provider_registry."
    with pytest.raises(RecordNormalizationException) as excinfo:
        _ = search_result_list.normalize(raise_on_error=True)

    assert e in str(excinfo.value)
    assert e in caplog.text

    search_result_error = (
        f"The normalization of the page {search_result.page} response result for provider, {search_result.provider_name} failed: "
        f"{e}"
    )

    search_result_list_error = (
        f"An error was encountered during the batch normalization of a search result list: {search_result_error}"
    )
    assert search_result_error in str(excinfo.value)
    assert search_result_list_error in str(excinfo.value)

    caplog.clear()

    assert processed_response.normalize(raise_on_error=False) == []
    warning_message = "Returning an empty list."
    assert warning_message in caplog.text

    caplog.clear()

    assert search_result_list.normalize(raise_on_error=False) == []
    assert search_result_error in caplog.text
    assert f"{e} Returning an empty list." in caplog.text


@pytest.fixture
def response_json(mock_complex_json_records: list[dict]) -> dict:
    """A basic JSON data set that enables the normalization testing for JSON records data after response retrieval."""
    response_json = {"records": mock_complex_json_records, "metadata": {"count": len(mock_complex_json_records)}}
    return response_json


@pytest.fixture
def default_search_coordinator(
    with_mock_academic_provider: None, mock_complex_json_records: list[dict]
) -> Generator[SearchCoordinator, None, None]:
    """A basic search coordinator that uses a temporary provider for testing common normalization scenarios."""
    provider_name = "mock_academic_provider"
    record_count = len(mock_complex_json_records)

    coordinator = SearchCoordinator(query="test-query", provider_name=provider_name, records_per_page=record_count)
    coordinator.responses.processor.value_delimiter = None  # type: ignore
    yield coordinator


@pytest.fixture
def setup_mocking(default_search_coordinator: SearchCoordinator, response_json: dict) -> Callable:
    """Creates a nested function used to mock search results using a coordinator, response JSON, and requests_mock."""

    @contextmanager
    def mocking_context(page: int = 1, json_data: dict | None = None) -> Generator[requests_mock.Mocker, None, None]:
        """Context manager that uses the coordinator as well as the response json to mock a response."""
        current_json_data = json_data or response_json
        prepared_search = default_search_coordinator.api.prepare_search(page=page)
        default_search_coordinator.responses.processor.value_delimiter = None  # type: ignore

        provider_config = provider_registry[default_search_coordinator.api.provider_name]
        assert provider_config and provider_config.field_map

        with requests_mock.Mocker() as m:
            m.get(
                prepared_search.url,
                json=current_json_data,
                headers={"content-type": "application/json"},
                status_code=200,
            )
            yield m

    return mocking_context


def test_search_normalization(default_search_coordinator, setup_mocking):
    """Verifies that the normalization of records occurs as intended through the full, orchestrated pipeline."""
    with setup_mocking(page=1) as _:
        response = default_search_coordinator.search(page=1)
        search_result_list = default_search_coordinator.search_pages(pages=[1])

    search_result = search_result_list[0]

    # will use the URL to resolve the response to the provider's field map
    normalized_records = response.normalize()
    normalized_records_two = search_result.normalize(update_records=False)
    normalized_records_three = search_result_list.normalize(update_records=False)

    assert (
        normalized_records
        and isinstance(normalized_records, list)
        and all(isinstance(record, dict) for record in normalized_records)
    )

    # the normalization with an ProcessedResponse/SearchResult/SearchResultList shouldn't affect the final result
    assert normalized_records == normalized_records_two
    assert normalized_records == normalized_records_three


def test_search_normalization_structure(default_search_coordinator, setup_mocking):
    """Verifies that the normalization of records returns a list of dictionaries with the required structure."""
    provider_config = provider_registry[default_search_coordinator.api.provider_name]
    assert provider_config and provider_config.field_map

    with setup_mocking(page=1) as _:
        response = default_search_coordinator.search(page=1, normalize_records=True)

    normalized_records = response.normalized_records
    assert normalized_records is response.normalized_records is response.normalize()  # extracts cached results

    # the number of records should equal that of the original record count
    assert len(normalized_records) == len(response.data)

    # all normalized record fields should be present in each record
    field_map = provider_config.field_map
    fields = field_map.fields
    assert all(field in record for field in fields for record in normalized_records)


def test_recursive_normalization_equality(default_search_coordinator, setup_mocking):
    """Tests whether the normalization of flattened and unflattened JSON records should return equal results."""

    provider_config = provider_registry[default_search_coordinator.api.provider_name]
    assert provider_config and provider_config.field_map
    test_processor = RecursiveDataProcessor(value_delimiter=None)

    with setup_mocking(page=1) as _:
        response = default_search_coordinator.search(page=1)

    assert isinstance(response, ProcessedResponse)

    # will use the URL to resolve the response to the provider's field map
    normalized_records = response.normalize()
    recursively_processed_records = test_processor(response.extracted_records)
    normalized_records_two = provider_config.field_map(recursively_processed_records)
    assert normalized_records == normalized_records_two

    assert normalized_records[0]["url"] and normalized_records[0]["url"] == normalized_records[0]["record_id"]
