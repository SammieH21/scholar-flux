from scholar_flux.api.models import (
    ProcessedResponse,
    ErrorResponse,
    SearchResult,
    SearchResultList,
)
from scholar_flux.api.providers import get_display_name
from copy import deepcopy
from typing import Any
import re
import pytest


@pytest.fixture
def extracted_records() -> list[dict[str, int]]:
    """Mocks the `extracted_records` attribute with list of dictionaries, each representing a record in the response."""
    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]
    return extracted_records


@pytest.fixture
def processed_records(extracted_records) -> list[dict[str, int]]:
    """Fixture for mocking the processed_records attribute in the creation of a ProcessedResponse."""
    processed_records = extracted_records.copy()
    return processed_records


@pytest.fixture
def normalized_records(processed_records) -> list[dict[str, int]]:
    """Fixture for mocking the normalized_records attribute in the creation of a ProcessedResponse."""
    normalized_records = [
        {str(key): value for key, value in record.items()} | {"provider_name": "test"} for record in processed_records
    ]

    return normalized_records


@pytest.fixture
def metadata() -> dict[str, Any]:
    """Mocks a simple metadata dictionary used in creating a success_response."""
    metadata = {"a": 1, "b": 2}
    return metadata


@pytest.fixture
def success_response(
    mock_successful_response, extracted_records, metadata, processed_records, normalized_records
) -> ProcessedResponse:
    """Fixture used to mock an `SuccessResponse` to be later encapsulated in a SearchResult."""
    success_response = ProcessedResponse(
        cache_key="test-cache-key",
        response=mock_successful_response,
        extracted_records=extracted_records,
        processed_records=processed_records,
        metadata=metadata,
        normalized_records=normalized_records,
    )
    return success_response


@pytest.fixture
def unauthorized_response(mock_unauthorized_response) -> ErrorResponse:
    """Fixture used to mock an `ErrorResponse` to be later encapsulated in a SearchResult."""
    unauthorized_response = ErrorResponse(
        response=mock_unauthorized_response,
        message="This is an unauthorized response",
        error="Unauthorized",
        cache_key="test-cache-key",
    )
    return unauthorized_response


@pytest.fixture
def search_result_success(extracted_records, processed_records, metadata) -> SearchResult:
    """Fixture that indicates that the retrieval and processing of the response was successful."""

    search_result_success = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=1,
        response_result=ProcessedResponse.from_response(
            cache_key="test-cache-key",
            status_code=200,
            url="https://www.example-url-test.com",
            extracted_records=extracted_records,
            processed_records=processed_records,
            metadata=metadata,
        ),
    )

    return search_result_success


@pytest.fixture
def search_result_error() -> SearchResult:
    """Fixture that indicates that an error occurred somewhere in the retrieval or processing of the API Response."""
    search_result_error = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=2,
        response_result=ErrorResponse.from_response(
            cache_key="test-cache-key", status_code=401, url="https://www.example-url-test.com"
        ),
    )

    return search_result_error


@pytest.fixture
def search_result_none() -> SearchResult:
    """Indicates that a request could not be retrieved as intended - logs should be checked in such scenarios"""
    return SearchResult(provider_name="test-provider", query="test-query", page=3, response_result=None)


@pytest.fixture
def mock_search_result_list() -> SearchResultList:
    """A list of plausible search results that uses registered provider names for testing the `select()` method."""
    query = "test query"
    providers = ["arXiv", "SpringerNature", "PubmedEfetch", "UnknownProvider"]

    return SearchResultList(
        SearchResult(page=1, provider_name=provider_name, query=query) for provider_name in providers
    )


def test_search_result_errors(unauthorized_response):
    """Tests the instantiation of SearchResult with `ErrorResponses` and verifies whether each attribute is retrievable.

    Also verifies whether error responses contain the logged errors involved and associated messages.

    """
    search_result_error = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=2,
        response_result=unauthorized_response,
    )

    # validating the attributes of the `search_result_error` instance that holds an ErrorResponse
    assert search_result_error != unauthorized_response  # the two aren't the same class, so this shouldn't equal
    assert search_result_error.data is None
    assert search_result_error.metadata is None
    assert search_result_error.processed_metadata is None
    assert search_result_error.total_query_hits is None
    assert search_result_error.records_per_page is None
    assert search_result_error.extracted_records is None
    assert search_result_error.response == unauthorized_response.response
    assert search_result_error.error == "Unauthorized"
    assert search_result_error.message == "This is an unauthorized response"
    assert len(search_result_error) == search_result_error.record_count == 0
    assert search_result_error.cache_key == "test-cache-key"

    # ensuring that the search_result_error is falsy
    assert isinstance(search_result_error, SearchResult) and not search_result_error


def test_search_result_success(success_response, extracted_records, metadata, processed_records, normalized_records):
    """Tests the instantiation of `SearchResults` with `ProcessedResponses` to verify if each attribute is retrievable.

    Also verifies whether processed responses contain the correct extracted and processed records and whether error
    responses contain the logged errors involved and associated messages.

    """

    search_result_success = SearchResult(
        provider_name="test-provider", query="test-query", page=1, response_result=success_response
    )

    # ensuring that the search_result_success is truthy
    assert search_result_success

    # validating elements of the search_result_success class
    assert isinstance(search_result_success, SearchResult) and search_result_success.response_result
    assert search_result_success.data == processed_records == search_result_success.processed_records
    assert search_result_success.normalized_records == normalized_records
    assert search_result_success.metadata == metadata
    assert search_result_success.parsed_response is None
    assert search_result_success.extracted_records == extracted_records
    assert search_result_success.response == success_response.response
    assert search_result_success.processed_metadata is None
    assert search_result_success.total_query_hits is None
    assert search_result_success.records_per_page is None
    assert search_result_success.error is None
    assert search_result_success.message is None

    assert (
        len(search_result_success)
        == len(search_result_success.data or [])
        == len(search_result_success.extracted_records or [])
        == search_result_success.record_count
    )

    assert search_result_success.cache_key == "test-cache-key"


@pytest.mark.parametrize(
    "provider_name",
    ("arxiv", "core", "crossref", "plos", "openalex", "pubmed", "pubmed_efetch", "springernature", "unknown_provider"),
)
def test_display_name_resolution(provider_name):
    """Verifies that each provider name successfully resolves back a human readable display name when available."""
    search_result = SearchResult(page=1, query="a query", provider_name=provider_name)
    assert search_result.display_name == get_display_name(provider_name) or provider_name


def test_invalid_search_list_elements():
    """Tests whether the `SearchResultList` correctly raises a type error when encountering invalid values."""
    result_list = SearchResultList()

    with pytest.raises(TypeError):
        result_list.append(1)  # type: ignore

    with pytest.raises(TypeError):
        result_list[0] = True  # type: ignore

    with pytest.raises(TypeError):
        result_list.extend([True, False])  # type: ignore


def test_default_with_search_fields():
    """Verifies that the behavior of `with_search_fields depends on the received type."""
    # Attempting to append the search result list's search fields should return None.
    search_result = SearchResult(query="q", page=1, provider_name="new")

    ### Treated as empty records ###
    defaults = {"page": 1, "provider_name": "new"}
    assert search_result.with_search_fields(None) == defaults
    assert search_result.with_search_fields({}) == defaults

    ### Treated as lists of records ###
    assert search_result.with_search_fields([]) == []
    assert search_result.with_search_fields([{"a": 1}, {"b": 2}]) == [{"a": 1} | defaults, {"b": 2} | defaults]

    with pytest.raises(TypeError):
        _ = search_result.with_search_fields(12345)  # type: ignore


def test_valid_search_list_elements(search_result_success, search_result_error, search_result_none):
    """Verifies whether the `SearchResultList` successfully adds SearchResult instances to the list."""
    result_list = SearchResultList()

    result_list.extend(SearchResultList([search_result_success, search_result_error]))
    result_list.append(search_result_error)  # duplicated value
    result_list[2] = search_result_none  # replacement value

    assert len(result_list) == 3
    assert result_list[-1].response_result is None

    filtered_records = result_list.filter()
    assert (
        isinstance(filtered_records[0], SearchResult)
        and isinstance(filtered_records[0].response_result, ProcessedResponse)
        and len(filtered_records[0].response_result.data or []) > 0
    )

    data_records = filtered_records[0].response_result.data or []  # type: ignore
    joined_records = result_list.join(include={"provider_name", "page"})

    response_record_total = sum(
        len(result.response_result.data or []) for result in filtered_records if result.response_result
    )

    assert len(joined_records) == response_record_total == result_list.record_count
    assert joined_records == [record | {"provider_name": "test-provider", "page": 1} for record in data_records]


def test_search_result_concatenation_invalid_objects():
    """Verifies that `__add__` raises a TypeError when encountering non-SearchResult objects."""
    result_list = SearchResultList()
    invalid_list = [1, 2, 3]

    with pytest.raises(
        TypeError,
        match=(
            "Encountered an error while attempting to concatenate search results to a SearchResultList: Expected an "
            "iterable of SearchResults, but not all elements in the iterable are SearchResult elements."
        ),
    ):
        _ = result_list + invalid_list  # type: ignore

    invalid_object = 123
    with pytest.raises(
        TypeError,
        match=(
            "Encountered an error while attempting to concatenate search results to a SearchResultList: Expected an "
            f"iterable of SearchResults, received an object of type {type(invalid_object)}"
        ),
    ):
        _ = result_list + invalid_object  # type: ignore


def test_search_result_selection():
    """Verifies elements of a SearchResultList can be selected based on query, provider, and/or page."""

    pages = list(range(1, 5))  # 1 to 4
    mock_providers = ["Provider_one", "ProviderTwo", "ProviderThree"]
    mock_queries = ["test-query-one", "test-query-two", "test-query-three"]
    search_result_list = SearchResultList(
        SearchResult(page=i, provider_name=provider_name, query=query)
        for i in pages
        for provider_name in mock_providers
        for query in mock_queries
    )
    filtered_search_results = search_result_list.select(page=1)

    assert len(mock_providers) * len(mock_queries) == len(filtered_search_results)

    assert all(
        SearchResult(page=1, provider_name=provider_name, query=query) in filtered_search_results
        for query in mock_queries
        for provider_name in mock_providers
    )

    # provider names should resolve with normalization
    filtered_search_results_two = search_result_list.select(query="test-query-one", provider_name="provider_one")
    assert len(pages) == len(filtered_search_results_two)
    filtered_search_results_two_pages = (search_result.page for search_result in filtered_search_results_two)
    assert all(page in filtered_search_results_two_pages for page in pages)

    for search_result in search_result_list:
        filtered_search_result = (
            search_result_list.select(query=search_result.query)
            .select(provider_name=search_result.provider_name)
            .select(page=search_result.page)
        )

        assert len(filtered_search_result) == 1 and filtered_search_result[0] == search_result


def test_search_result_prefix_filtering(mock_search_result_list):
    """Verifies that `select` retrieves search results for provider names starting with a key."""

    # Should be able to loosely retrieve names for providers using .startswith() after normalization
    pubmed_selection = mock_search_result_list.select(provider_name="pubmed")
    assert pubmed_selection and pubmed_selection[0].provider_name == "PubmedEfetch"

    springer_nature_selection = mock_search_result_list.select(provider_name="springer")
    assert springer_nature_selection and springer_nature_selection[0].provider_name == "SpringerNature"

    # Should still be retrievable and match exactly after normalization
    assert springer_nature_selection == mock_search_result_list.select(provider_name="Springer_Nature")

    assert (
        mock_search_result_list.select(provider_name="arxiv|springer|pubmed", regex=True)
        == mock_search_result_list[:-1]
    )

    # Edge Case (UnknownProvider isn't registered)
    assert mock_search_result_list[-1:] == mock_search_result_list.select(provider_name="UnknownProvider")

    # Exact matches only
    assert not mock_search_result_list.select(provider_name="arx", fuzzy=False)
    assert mock_search_result_list[:1] == mock_search_result_list.select(provider_name="arxiv", fuzzy=False)

    # Edge cases
    assert mock_search_result_list.select(provider_name="", fuzzy=False) == []
    assert mock_search_result_list.select(provider_name="", fuzzy=True) == []


def test_search_result_fuzzy_filtering(mock_search_result_list):
    """Verifies that `select` correctly retrieves registered provider names via pattern matching when possible."""
    # When using a pattern, should automatically switch to regex pattern search
    registered_providers = mock_search_result_list[:-1]
    pattern = re.compile("arxiv|springer|pubmed")
    assert registered_providers == mock_search_result_list.select(provider_name=pattern)

    # Only with `regex=True` are regular strings used as patterns
    assert mock_search_result_list.select(provider_name=pattern.pattern, regex=True) == registered_providers

    # Shouldn't find anything since this is a regex pattern, but regex pattern matching is disabled
    assert mock_search_result_list.select(provider_name=re.compile("arxiv|springer|pubmed"), regex=False) == []

    arxiv_list = mock_search_result_list.select(provider_name="arxiv", fuzzy=False)
    assert arxiv_list[0].provider_name == "arXiv"
    assert mock_search_result_list.select(provider_name=re.compile("arXiv")) == arxiv_list

    # fuzzy=False means that only exact matches would be checked. Patterns are then converted directly to strings
    assert mock_search_result_list.select(provider_name=re.compile("arXiv"), fuzzy=False) == arxiv_list

    # There should be no providers that match an empty string
    assert mock_search_result_list.select(provider_name=re.compile(""), fuzzy=False) == []


def test_search_result_addition():
    """Verifies that two SearchResultList instances can be joined using the overridden `__add__` operator."""
    pages = list(range(1, 3))

    search_result_list = SearchResultList(SearchResult(page=i, provider_name="Provider 1", query="q") for i in pages)

    search_result_list2 = SearchResultList(SearchResult(page=i, provider_name="Provider 2", query="q") for i in pages)

    search_result_iter2 = iter(SearchResult(page=i, provider_name="Provider 2", query="q") for i in pages)

    search_result_list_concat = search_result_list + search_result_list2
    assert isinstance(search_result_list_concat, SearchResultList)
    search_result_list_concat = search_result_list + search_result_list2
    assert search_result_list_concat == SearchResultList(list(search_result_list) + list(search_result_list2))
    assert all(
        search_result_list_concat[i] == result
        for i, result in enumerate(list(search_result_list) + list(search_result_list2))
    )

    search_result_list_concat2 = search_result_list + search_result_iter2
    assert search_result_list_concat == search_result_list_concat2


def test_search_result_copy():
    """Verifies that the `__copy__` method correctly creates a shallow copy of the current SearchResultList"""
    pages = list(range(1, 5))  # 1 to 4
    mock_providers = ["Provider_one", "ProviderTwo", "ProviderThree"]
    search_result_list = SearchResultList(
        SearchResult(page=i, provider_name=provider_name, query="q") for i in pages for provider_name in mock_providers
    )
    copied_search_result_list = search_result_list.copy()
    copied_search_result_list2 = deepcopy(search_result_list)

    assert copied_search_result_list == search_result_list and id(copied_search_result_list) != id(search_result_list)
    assert copied_search_result_list == copied_search_result_list2
    assert id(copied_search_result_list) != id(copied_search_result_list2)
    assert isinstance(copied_search_result_list, SearchResultList)
    assert isinstance(copied_search_result_list2, SearchResultList)
