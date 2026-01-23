"""Tests for PLOS field map normalization and post-processing.

This test suite covers:
1. URL reconstruction from DOI
2. Year extraction from publication dates
3. Full normalization integration

"""

import pytest
from scholar_flux.api.normalization.plos_field_map import field_map as plos_field_map, PLOSFieldMap
from scholar_flux.utils.helpers import extract_year


# ==================== Fixtures ====================


@pytest.fixture
def plos_sample_record():
    """Sample PLOS API record for integration testing."""
    return {
        "id": "10.1371/journal.pone.0123456",
        "title_display": "Sample PLOS Article",
        "publication_date": "2024-12-18T00:00:00Z",
        "author_display": ["Author One", "Author Two"],
    }


@pytest.fixture
def plos_complete_record():
    """Complete PLOS record with all available fields."""
    return {
        "id": "10.1371/journal.pone.0298765",
        "title_display": "Complete PLOS ONE Article: A Comprehensive Study",
        "abstract": "This study investigates novel methodologies for data analysis in biological research.",
        "publication_date": "2024-06-15T00:00:00Z",
        "author_display": ["Smith, John", "Johnson, Jane", "Williams, Robert"],
        "journal": "PLOS ONE",
        "article_type": "Research Article",
        "subject": ["Biology", "Computational Biology", "Data Science"],
        "eissn": "1932-6203",
        "volume": "19",
        "issue": "6",
        "elocation_id": "e0298765",
        "score": 15.234,
    }


@pytest.fixture
def plos_minimal_record():
    """Minimal PLOS record with only required fields."""
    return {
        "id": "10.1371/journal.pone.0111111",
        "title_display": "Minimal PLOS Article",
        "publication_date": "2024",
    }


# ==================== Tests for URL Reconstruction ====================


@pytest.mark.parametrize(
    "doi, expected",
    (
        ("10.1371/journal.pone.0123456", "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0123456"),
        # Edge cases that should return None
        (None, None),
        ("", None),
        (["not", "a", "valid", "url"], None),  # concatenation with the base URL should not produce a valid URL
        ({}, None),
    ),
)
def test_reconstruct_plos_url_valid_doi(doi, expected):
    """Verifies that URLs are only reconstructed if the produced URL is valid and the DOI exists as a string."""
    record = {"doi": doi} if not isinstance(doi, dict) else doi
    url = PLOSFieldMap.reconstruct_plos_url(record)
    assert url == expected


# ==================== Tests for Year Extraction ====================


def test_extract_year_from_publication_date(plos_sample_record):
    """Verifies with a mocked PLOS record that the year is correctly extracted from the publication_date field."""
    year = extract_year(plos_sample_record["publication_date"])
    assert year == 2024


def test_extract_year_iso_datetime():
    """Verifies that the year is correctly extracted from an ISO datetime string with timezone information."""
    assert extract_year("2024-06-15T00:00:00Z") == 2024


def test_extract_year_year_only():
    """Verifies that the year is correctly extracted when only the year is provided as input."""
    assert extract_year("2024") == 2024


# ==================== Tests for Field Transformations ====================


def test_plos_transformations(plos_sample_record):
    """Verifies that field transformations such as year extraction and URL reconstruction work as intended."""
    year = extract_year(plos_sample_record["publication_date"])
    assert year == 2024

    url = PLOSFieldMap.reconstruct_plos_url({"doi": plos_sample_record["id"]})
    assert url == f"https://journals.plos.org/plosone/article?id={plos_sample_record['id']}"


# ==================== Full Normalization Integration ====================


def test_plos_record_normalization(plos_sample_record):
    """Verifies that normalization correctly processes the mocked PLOS record and extracts the year and URL."""
    normalized_record = plos_field_map.normalize_record(plos_sample_record)

    assert normalized_record["year"] == 2024
    assert normalized_record["url"] == f"https://journals.plos.org/plosone/article?id={normalized_record['doi']}"


def test_plos_complete_normalization(plos_complete_record):
    """Verifies with a mocked, complete PLOS record that all fields are correctly normalized (IDs, metadata, etc.)."""
    normalized = plos_field_map.normalize_record(plos_complete_record)

    # Core identifiers
    assert normalized["doi"] == "10.1371/journal.pone.0298765"
    assert normalized["record_id"] == "10.1371/journal.pone.0298765"
    assert normalized["url"] == "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0298765"

    # Bibliographic
    assert normalized["title"] == "Complete PLOS ONE Article: A Comprehensive Study"
    assert "novel methodologies" in normalized["abstract"]
    assert normalized["authors"] == ["Smith, John", "Johnson, Jane", "Williams, Robert"]

    # Publication metadata
    assert normalized["journal"] == "PLOS ONE"
    assert normalized["publisher"] == "Public Library of Science"  # Default value
    assert normalized["year"] == 2024

    # Content classification
    assert "Biology" in normalized["keywords"]
    assert normalized["subjects"] == "Research Article"

    # Access (PLOS is always open access)
    assert normalized["open_access"] is True

    # Document metadata
    assert normalized["record_type"] == "Research Article"


def test_plos_minimal_normalization(plos_minimal_record):
    """Verifies that PLOS record normalization handles missing fields gracefully and extracts available data."""
    normalized = plos_field_map.normalize_record(plos_minimal_record)

    assert normalized["record_id"] == "10.1371/journal.pone.0111111"
    assert normalized["doi"] == "10.1371/journal.pone.0111111"
    assert normalized["title"] == "Minimal PLOS Article"
    assert normalized["year"] == 2024
    assert normalized["url"] == "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0111111"
    assert normalized["abstract"] is None
    assert normalized["authors"] is None


def test_plos_batch_normalization(plos_sample_record, plos_minimal_record, plos_complete_record):
    """Verifies that batch normalization processes multiple mocked records correctly and consistently."""
    records = [plos_sample_record, plos_minimal_record, plos_complete_record]
    normalized_list = plos_field_map.normalize_records(records)

    assert len(normalized_list) == 3
    assert all(n["year"] == 2024 for n in normalized_list)
    assert all(n["open_access"] is True for n in normalized_list)


# ==================== Edge Cases ====================


def test_plos_empty_author_list():
    """Verifies that normalization handles an empty author list extraction gracefully."""
    record = {"id": "10.1371/journal.pone.0000000", "title_display": "No Authors", "author_display": []}
    normalized = plos_field_map.normalize_record(record)
    assert normalized["authors"] is None or normalized["authors"] == []


def test_plos_single_author():
    """Verifies that normalization correctly handles a single author in the author list."""
    record = {
        "id": "10.1371/journal.pone.0000001",
        "title_display": "Solo Author",
        "author_display": ["Solo Researcher"],
    }
    normalized = plos_field_map.normalize_record(record)
    assert "Solo Researcher" in str(normalized["authors"])


def test_plos_empty_subjects():
    """Tests that normalization handles an empty subject array gracefully."""
    record = {"id": "10.1371/journal.pone.0000002", "title_display": "No Subjects", "subject": []}
    normalized = plos_field_map.normalize_record(record)
    assert normalized["keywords"] is None or normalized["keywords"] == []
