"""Tests for Springer Nature field map normalization and post-processing.

Test suite covering:
1. Year extraction from publication dates
2. Open access boolean conversion
3. URL extraction from nested structures
4. Full normalization integration

"""

import pytest

from scholar_flux.api.normalization.springer_nature_field_map import (
    SpringerNatureFieldMap,
)
from scholar_flux.api.normalization.springer_nature_field_map import (
    field_map as springer_nature_field_map,
)

# ==================== Fixtures ====================


@pytest.fixture
def springer_nature_sample_record():
    """A sample, mocked Springer Nature API record for integration testing."""
    return {
        "doi": "10.1234/example",
        "title": "Sample Article",
        "publicationDate": "2026-03-01",
        "openaccess": "true",
        "url": [{"value": "http://example.com/article"}, {"value": "http://backup.com/article"}],
        "creators": {"creator": ["Author One", "Author Two"]},
    }


@pytest.fixture
def springer_nature_minimal_record():
    """A minimal, mocked Springer Nature record with required fields only."""
    return {
        "identifier": "art:10.1234/example",
        "title": "Minimal Article",
        "publicationDate": "2024",
    }


@pytest.fixture
def springer_nature_complete_record():
    """Complete, mocked Springer Nature record containing all fields for normalization."""
    return {
        "doi": "10.1038/s41586-024-07890-1",
        "identifier": "art:10.1038/s41586-024-07890-1",
        "title": "Complete Springer Nature Article",
        "abstract": "This is a comprehensive abstract covering the research methodology and findings.",
        "publicationDate": "2024-06-15",
        "onlineDate": "2024-06-10",
        "openaccess": "true",
        "url": [{"value": "https://www.nature.com/articles/s41586-024-07890-1"}],
        "creators": {"creator": ["Smith, John", "Johnson, Jane", "Williams, Robert"]},
        "publicationName": "Nature",
        "publisher": "Springer Nature",
        "keyword": ["climate", "biodiversity", "ecology"],
        "subjects": ["Environmental Science", "Biology"],
        "contentType": "Article",
        "language": "en",
        "copyright": "© 2024 The Authors",
        "volume": "630",
        "number": "8015",
        "startingPage": "123",
        "endingPage": "130",
        "issn": "0028-0836",
        "eIssn": "1476-4687",
    }


# ==================== Tests for Open Access Validation ====================


@pytest.mark.parametrize(
    "status,expected",
    (
        ("true", True),
        ("false", False),
        (True, True),
        (False, False),
        ("TRUE", True),
        ("FALSE", False),
        ("None", None),
        ("N/A", None),
        ("UNKNOWN", None),
        (23, None),  # random edge case where the type is unexpected
        ({23, 45, 6}, None),  # incorrect data type
    ),
)
def test_validate_open_access_status(status, expected):
    """Validates open-access extraction status for common and unlikely openaccess fields."""
    record = {"open_access": status}
    open_access = SpringerNatureFieldMap.extract_open_access(record)
    assert open_access is expected


# ==================== Tests for URL Extraction ====================


def test_extract_nested_springer_nature_primary_url(springer_nature_sample_record):
    """Verifies that `extract_primary_url` correctly traverses Springer Nature URL fields to get the first valid URL."""
    url = SpringerNatureFieldMap.extract_primary_url(springer_nature_sample_record, "url")
    assert url == "http://example.com/article"


@pytest.mark.parametrize("sep", (";", ",", "; ", ", ", "|"))
def test_extract_valid_first_valid_from_multi_url_string(sep):
    """Verifies that `extract_url` correctly retrieves the first valid URL from a delimited string of URLs."""
    record = {"url": f"https://example1.com/{sep}https://example2.com/{sep}https://example3.com/"}
    url = SpringerNatureFieldMap.extract_url(record, ["url", 0])
    assert url == "https://example1.com/"


def test_extract_url_missing():
    """Verifies that URL extraction returns None if a valid URL cannot be found."""
    record = {"title": "No URL"}
    url = SpringerNatureFieldMap.extract_url(record, ["url", 0, "value"], ["url", 0], ["url"])
    assert url is None


def test_extract_url_lookahead_prevents_splitting():
    """Verifies that URLs that are delimited use a positive lookahead `http` that prevents splitting URLs mid-domain."""
    record = {"url": "http://example.com/page;param=value; http://backup.com"}
    # Should NOT split at the semicolon in the URL parameter
    url = SpringerNatureFieldMap.extract_url(record, pattern_delimiter="; *")
    assert url == "http://example.com/page;param=value"


def test_extract_url_fallback_paths():
    """Ensures that fallback paths are attempted for extraction in order.

    `url` should be resolved first for example.

    """
    record = {
        "url": [{"format": "html", "value": "http://example.com"}, {"format": "pdf", "value": "http://example.com/pdf"}]
    }
    # Should try ["url"] first (fails), then ["url", 0] (fails), then ["url", 0, "value"] (succeeds)
    url = SpringerNatureFieldMap.extract_url(record, ["url"], ["url", 0], ["url", 0, "value"])
    assert url == "http://example.com"


def test_extract_url_invalid_urls_skipped():
    """Verifies that invalid URL fields in list formats are skipped."""
    record = {"url": ["not-a-url", "http://valid.com"]}
    url = SpringerNatureFieldMap.extract_url(record)
    assert url == "http://valid.com"


# ==================== Tests for Field Transformations ====================


def test_springer_nature_transformations(springer_nature_sample_record):
    """Verifies basic data extraction for Springer Nature field transformations."""
    record = springer_nature_sample_record

    year = SpringerNatureFieldMap.extract_year(record, "publicationDate")
    assert year == 2026

    open_access = SpringerNatureFieldMap.extract_open_access(record, "openaccess")
    assert open_access is True

    url = SpringerNatureFieldMap.extract_url(record, ["url", 0, "value"], ["url", 0], ["url"])
    assert url == "http://example.com/article"


# ==================== Edge Cases ====================


def test_springer_nature_null_open_access():
    """Verifies that normalizing a record with an empty open-access field will gracefully return None."""
    record = {"identifier": "test", "title": "Test", "publicationDate": "2024", "openaccess": None}
    normalized = springer_nature_field_map.normalize_record(record)
    assert normalized["open_access"] is None


def test_springer_nature_empty_url_list():
    """Verifies that normalizing a record with an empty URL list returns None."""
    record = {"identifier": "test", "title": "Test", "publicationDate": "2024", "url": []}
    normalized = springer_nature_field_map.normalize_record(record)
    assert normalized["url"] is None


def test_springer_nature_single_author():
    """Verifies that the normalization of the author field can successfully handle a single-author string."""
    record = {"identifier": "test", "title": "Test", "publicationDate": "2024", "creators": {"creator": "Solo Author"}}
    normalized = springer_nature_field_map.normalize_record(record)
    assert "Solo Author" in str(normalized["authors"])


# ==================== Full Normalization Integration ====================


def test_springer_nature_record_normalization(springer_nature_sample_record):
    """Integration test for the normalization of a mocked Springer Nature record."""
    normalized_record = springer_nature_field_map.normalize_record(springer_nature_sample_record)

    assert normalized_record["year"] == 2026
    assert normalized_record["open_access"] is True
    assert normalized_record["url"] == "http://example.com/article"


def test_springer_nature_complete_normalization(springer_nature_complete_record):
    """Tests the full normalization pipeline using a mocked record with a complete set of fields for normalization."""
    normalized = springer_nature_field_map.normalize_record(springer_nature_complete_record)

    # Core identifiers
    assert normalized["doi"] == "10.1038/s41586-024-07890-1"
    assert normalized["record_id"] == "art:10.1038/s41586-024-07890-1"
    assert normalized["url"] == "https://www.nature.com/articles/s41586-024-07890-1"

    # Bibliographic
    assert normalized["title"] == "Complete Springer Nature Article"
    assert "comprehensive abstract" in normalized["abstract"]
    assert normalized["authors"] == ["Smith, John", "Johnson, Jane", "Williams, Robert"]

    # Publication metadata
    assert normalized["journal"] == "Nature"
    assert normalized["publisher"] == "Springer Nature"
    assert normalized["year"] == 2024
    assert normalized["date_published"] == "2024-06-15"
    assert normalized["date_created"] == "2024-06-10"

    # Content classification
    assert "climate" in normalized["keywords"]
    assert "Environmental Science" in normalized["subjects"]

    # Access
    assert normalized["open_access"] is True
    assert normalized["license"] == "© 2024 The Authors"

    # Document metadata
    assert normalized["record_type"] == "Article"
    assert normalized["language"] == "en"


def test_springer_nature_minimal_normalization(springer_nature_minimal_record):
    """Verifies the Springer Nature normalization pipeline using a minimal, mocked record."""
    normalized = springer_nature_field_map.normalize_record(springer_nature_minimal_record)

    assert normalized["record_id"] == "art:10.1234/example"
    assert normalized["title"] == "Minimal Article"
    assert normalized["year"] == 2024
    assert normalized["doi"] is None
    assert normalized["abstract"] is None
    assert normalized["url"] is None


def test_springer_nature_batch_normalization(
    springer_nature_sample_record,
    springer_nature_minimal_record,
    springer_nature_complete_record,
):
    """Tests Springer Nature normalization for a batch of three mocked records of different types."""
    records = [springer_nature_sample_record, springer_nature_minimal_record, springer_nature_complete_record]
    normalized_list = springer_nature_field_map.normalize_records(records)

    assert len(normalized_list) == 3
    assert normalized_list[0]["year"] == 2026
    assert normalized_list[1]["year"] == 2024
    assert normalized_list[2]["year"] == 2024
