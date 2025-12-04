import pytest
from scholar_flux.api.models import ResponseMetadataMap
from scholar_flux.utils import PathUtils
from typing import Any, Optional
from pydantic import ValidationError


@pytest.fixture
def metadata_map() -> ResponseMetadataMap:
    """A metadata map created with the aim of testing response metadata processing features."""
    metadata_map = ResponseMetadataMap(total_query_hits="Hits", records_per_page="pageSize")
    return metadata_map


@pytest.fixture
def nested_metadata_map() -> ResponseMetadataMap:
    """A metadata map created with the aim of testing nested metadata processing features."""
    nested_metadata_map = ResponseMetadataMap(
        total_query_hits="statistics.Hits", records_per_page="statistics.options.pageSize"
    )
    return nested_metadata_map


@pytest.fixture
def simple_metadata_dict() -> dict[str, Any]:
    """Flat metadata fixture containing hits and page size as strings."""
    simple_metadata_dict = {"Hits": "27", "pageSize": "4"}
    return simple_metadata_dict


@pytest.fixture
def nested_metadata_dict() -> dict[str, Any]:
    """Nested metadata fixture containing hits and page size in nested structures."""
    nested_metadata_dict = {"statistics": {"Hits": "27", "options": {"pageSize": "4"}}}
    return nested_metadata_dict


@pytest.fixture
def nested_metadata_dict_after_flattening() -> dict[str, Any]:
    """Flattened metadata fixture with dot-notation keys for hits and page size."""
    nested_metadata_dict_after_flattening = {"statistics.Hits": "27", "statistics.options.pageSize": 4}
    return nested_metadata_dict_after_flattening


def test_metadata_map_optional_string_constraint():
    """Verifies that assigning non-string elements to query hits and records per page raise a ValidationError."""
    with pytest.raises(ValidationError):
        _ = ResponseMetadataMap(total_query_hits=[])  # type: ignore
    with pytest.raises(ValidationError):
        _ = ResponseMetadataMap(records_per_page=[])  # type: ignore


def test_response_metadata_query_hits_retrieval(
    metadata_map: ResponseMetadataMap, simple_metadata_dict: dict[str, Any]
):
    """Tests whether `total_query_hits` can be extracted as intended."""
    assert metadata_map.calculate_query_hits(simple_metadata_dict) == 27


def test_response_metadata_nested_query_hits_retrieval(
    nested_metadata_map: ResponseMetadataMap, nested_metadata_dict: dict[str, Any]
):
    """Tests whether `total_query_hits` can be extracted as intended."""
    assert nested_metadata_map.calculate_query_hits(nested_metadata_dict) == 27


def test_response_records_per_page_retrieval(metadata_map: ResponseMetadataMap, simple_metadata_dict: dict[str, Any]):
    """Verifies that records-per-page returns the expected type given metadata containing a valid page size field."""
    page_parameter = metadata_map.records_per_page or ""
    page_size = int(simple_metadata_dict[page_parameter])
    assert metadata_map.calculate_records_per_page(simple_metadata_dict) == page_size


def test_response_nested_records_per_page_retrieval(
    nested_metadata_map: ResponseMetadataMap, nested_metadata_dict: dict[str, Any]
):
    """Verifies that records-per-page returns the expected type given metadata containing a valid page size field."""
    full_path = nested_metadata_map.records_per_page or ""
    (statistics_key, metadata_key, page_parameter) = PathUtils.path_split(full_path)
    page_size = int(nested_metadata_dict[statistics_key][metadata_key][page_parameter])
    assert nested_metadata_map.calculate_records_per_page(nested_metadata_dict) == page_size


def test_flattened_response_records_per_page_retrieval(
    nested_metadata_map: ResponseMetadataMap, nested_metadata_dict_after_flattening: dict[str, Any]
):
    """Verifies that records-per-page returns the expected type given metadata containing a valid page size field."""
    page_parameter = nested_metadata_map.records_per_page or ""
    page_size = int(nested_metadata_dict_after_flattening[page_parameter])
    assert nested_metadata_map.calculate_records_per_page(nested_metadata_dict_after_flattening) == page_size


@pytest.mark.parametrize("parameter_value", ("non-existent-metadata-parameter", "", None))
def test_response_metadata_unsuccessful_query_hits_retrieval(
    parameter_value: Optional[str], simple_metadata_dict: dict[str, Any]
):
    """Verifies that empty or missing `total_query_hits` parameters resolve to None."""
    assert ResponseMetadataMap(total_query_hits=parameter_value).calculate_query_hits(simple_metadata_dict) is None


def test_response_metadata_unsuccessful_nested_parameter_retrieval(
    nested_metadata_map: ResponseMetadataMap, simple_metadata_dict: dict[str, Any]
):
    """Verifies that missing nested parameters resolve to None."""
    assert nested_metadata_map.calculate_query_hits(simple_metadata_dict) is None
    assert nested_metadata_map.calculate_records_per_page(simple_metadata_dict) is None


def test_calculate_query_hits_wrong_type(metadata_map: ResponseMetadataMap):
    """Verifies that `calculate_query_hits` returns `None` if an incorrect input type is received."""
    assert metadata_map.calculate_query_hits([1, 2, 3]) is None  # type: ignore
    assert metadata_map.calculate_query_hits(None) is None  # type: ignore


def test_calculate_records_per_page_wrong_type(metadata_map: ResponseMetadataMap):
    """Verifies that `calculate_records_per_page` returns `None` if an incorrect input type is received."""
    assert metadata_map.calculate_records_per_page([1, 2, 3]) is None  # type: ignore
    assert metadata_map.calculate_records_per_page(None) is None  # type: ignore


@pytest.mark.parametrize(("page", "expected_pages_remaining"), ((1, 6), (5, 2), (7, 0), (9, 0)))
def test_calculate_pages_remaining(
    page: int, expected_pages_remaining: int, metadata_map: ResponseMetadataMap, simple_metadata_dict: dict[str, Any]
):
    """Tests whether the metadata fields can be read and computed using the response metadata map."""
    assert metadata_map.calculate_pages_remaining(page=page, metadata=simple_metadata_dict) == expected_pages_remaining


def test_calculate_pages_remaining_wrong_type(metadata_map: ResponseMetadataMap, simple_metadata_dict: dict[str, Any]):
    """Verifies that `calculate_pages_remaining` returns `None` if an incorrect input type is received."""
    # gracefully return None given a missing `records_per_page` or `total_query_hits` metadata field
    assert metadata_map.calculate_pages_remaining(page=1) is None  # type: ignore
    # gracefully return None when `page` is missing
    assert metadata_map.calculate_pages_remaining(page=None, metadata=simple_metadata_dict) is None  # type: ignore


@pytest.mark.parametrize(
    ("page", "total_query_hits", "records_per_page", "expected_pages_remaining"),
    (
        (0, 20, 5, 4),
        (3, 50, 10, 2),
        (5, 10, 2, 0),
        (7, 40, 6, 0),
    ),
)
def test_pages_remaining(page: int, total_query_hits: int, records_per_page: int, expected_pages_remaining: int):
    """Validates the calculation of the number of remaining pages from page size, query hits, and page number."""
    assert (
        ResponseMetadataMap._calculate_pages_remaining(
            page=page,
            total_query_hits=total_query_hits,
            records_per_page=records_per_page,
        )
        == expected_pages_remaining
    )
