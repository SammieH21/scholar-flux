"""Tests for OpenAlex field map normalization and post-processing.

This test suite covers:
1. Abstract reconstruction from inverted index
2. DOI normalization (prefix stripping)
3. Author list filtering
4. PMID extraction
5. Integration with real record structures

"""

import pytest
from scholar_flux.api.normalization.open_alex_field_map import (
    OpenAlexFieldMap,
    field_map as openalex_field_map,
)

# ==================== Fixtures ========================================


@pytest.fixture
def openalex_sample_open_access_record():
    """Fixture of an OpenAlex mock API response for an open access article."""
    return {
        "id": "https://openalex.org/W2741809807",
        "doi": "https://doi.org/10.1371/journal.pone.0185809",
        "title": "The impact of climate change on global biodiversity patterns",
        "publication_year": 2023,
        "publication_date": "2023-06-15",
        "created_date": "2023-06-10",
        "language": "en",
        "type": "article",
        "is_retracted": False,
        "cited_by_count": 42,
        "abstract_inverted_index": {
            "Climate": [0],
            "change": [1],
            "is": [2],
            "affecting": [3],
            "biodiversity": [4],
            "globally": [5],
            ".": [6],
        },
        "authorships": [
            {
                "author": {"display_name": "Maria García"},
                "institutions": [{"display_name": "University of Barcelona"}],
            },
            {
                "author": {"display_name": "John Smith"},
                "institutions": [{"display_name": "MIT"}],
            },
        ],
        "primary_location": {
            "source": {
                "display_name": "PLOS ONE",
                "host_organization_name": "Public Library of Science",
                "issn": ["1932-6203"],
                "issn_l": "1932-6203",
            },
            "landing_page_url": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0185809",
            "license": "cc-by",
        },
        "open_access": {
            "is_oa": True,
            "oa_status": "gold",
        },
        "keywords": [
            {"display_name": "climate change"},
            {"display_name": "biodiversity"},
        ],
        "topics": [
            {"display_name": "Ecology"},
            {"display_name": "Conservation Biology"},
        ],
        "ids": {
            "openalex": "https://openalex.org/W2741809807",
            "pmid": "https://pubmed.ncbi.nlm.nih.gov/29241234",
            "mag": "2741809807",
        },
        "biblio": {
            "volume": "18",
            "issue": "6",
            "first_page": "e0185809",
            "last_page": None,
        },
        "referenced_works_count": 85,
        "fwci": 1.23,
    }


@pytest.fixture
def openalex_sample_closed_access_record():
    """Raw OpenAlex mock API response for a mocked, closed access article."""
    return {
        "id": "https://openalex.org/W1234567890",
        "doi": "https://doi.org/10.1016/j.example.2024.01.001",
        "title": "Subscription-only research findings",
        "publication_year": 2024,
        "publication_date": "2024-01-15",
        "created_date": "2024-01-10",
        "language": "en",
        "type": "article",
        "is_retracted": False,
        "cited_by_count": 5,
        "abstract_inverted_index": None,
        "authorships": [
            {
                "author": {"display_name": "Jane Doe"},
                "institutions": [{"display_name": "Harvard University"}],
            },
        ],
        "primary_location": {
            "source": {
                "display_name": "Journal of Expensive Research",
                "host_organization_name": "Elsevier",
                "issn": ["0001-0002"],
                "issn_l": "0001-0002",
            },
            "landing_page_url": "https://example.com/article",
            "license": None,
        },
        "open_access": {
            "is_oa": False,
            "oa_status": "closed",
        },
        "keywords": [],
        "topics": [],
        "ids": {
            "openalex": "https://openalex.org/W1234567890",
        },
        "biblio": {
            "volume": "100",
            "issue": "1",
            "first_page": "1",
            "last_page": "15",
        },
        "referenced_works_count": 30,
    }


@pytest.fixture
def openalex_sample_retracted_record():
    """Raw OpenAlex mock API response for a mocked, retracted article."""
    return {
        "id": "https://openalex.org/W9999999999",
        "doi": "https://doi.org/10.1234/retracted.2020",
        "title": "Study with fabricated data (RETRACTED)",
        "publication_year": 2020,
        "publication_date": "2020-03-01",
        "created_date": "2020-02-25",
        "language": "en",
        "type": "article",
        "is_retracted": True,
        "cited_by_count": 0,
        "abstract_inverted_index": {
            "RETRACTED": [0],
            ":": [1],
            "This": [2],
            "article": [3],
            "was": [4],
            "retracted": [5],
            ".": [6],
        },
        "authorships": [
            {"author": {"display_name": "Fraudulent Author"}, "institutions": []},
        ],
        "primary_location": {
            "source": {
                "display_name": "Journal of Dubious Claims",
                "host_organization_name": "Predatory Publisher",
            },
            "landing_page_url": "https://example.com/retracted",
            "license": "cc-by",
        },
        "open_access": {
            "is_oa": True,
            "oa_status": "gold",
        },
        "ids": {
            "openalex": "https://openalex.org/W9999999999",
        },
    }


@pytest.fixture
def openalex_sample_record_minimal():
    """Fixture for a minimal OpenAlex field map containing only an ID and title."""
    return {
        "id": "https://openalex.org/W0000000001",
        "title": "Minimal Record",
    }


# ==================== Tests for Open Access Validation ====================


@pytest.mark.parametrize(
    "status,expected",
    (
        ("diamond", True),
        ("gold", True),
        ("green", True),
        ("hybrid", True),
        ("bronze", True),
        ("closed", False),
        ("True", True),
        ("False", False),
        ("None", None),
        ("N/A", None),
        ("UNKNOWN", None),
        (43, None),  # random edge case where the type is unexpected
        ([28], None),  # incorrect data type
    ),
)
def test_validate_open_access_status(status, expected):
    """Validates open-access extraction status for common and unlikely OpenAlex open access identifiers."""
    record = {"open_access": status}
    open_access = OpenAlexFieldMap.extract_open_access(record)
    assert open_access is expected


# ==================== Abstract Reconstruction ====================


@pytest.mark.parametrize(
    "abstract_inverted_index,expected",
    [
        # Standard reconstruction
        ({"Hello": [0], "world": [1]}, "Hello world"),
        # Punctuation is generally appended to the surrounding word in OpenAlex inverted indexes
        ({"hello!": [3], "hello,": [2], "Hello,": [0]}, "Hello, hello, hello!"),
        # Repeated words at multiple positions
        (
            {"the": [0, 3], "cat": [1], "sat": [2]},
            "the cat sat the",
        ),
        # Single word
        ({"Abstract": [0]}, "Abstract"),
        # Empty/None cases
        ({}, None),
        ("", None),
        (None, None),
    ],
)
def test_reconstruct_abstract(abstract_inverted_index, expected):
    """Uses parametrized tests to verify that abstract inverted index reconstruction produces the expected abstracts."""

    record = (
        abstract_inverted_index
        if abstract_inverted_index == {}  # test an empty dictionary separately (edge case where a record is empty)
        else {"abstract_inverted_index": abstract_inverted_index}  # for all others, nest the value as a field
    )
    assert OpenAlexFieldMap.reconstruct_abstract(record) == expected


def test_reconstruct_abstract_real_world():
    """Verifies abstract reconstruction with realistic inverted index."""
    record = {
        "abstract_inverted_index": {
            "This": [0],
            "study": [1, 15],
            "examines": [2],
            "the": [3],
            "effects": [4],
            "of": [5, 13],
            "climate": [6],
            "change": [7],
            "on": [8],
            "biodiversity": [9],
            "The": [11],
            "results": [12],
            "this": [14],
            ".": [10, 16, 17, 18],
        }
    }
    result = OpenAlexFieldMap.reconstruct_abstract(record)
    assert result == "This study examines the effects of climate change on biodiversity. The results of this study..."


def test_reconstruct_abstract_filters_invalid_positions():
    """Verifies that abstract reconstruction skips non-integer index positions."""
    record = {
        "abstract_inverted_index": {
            "valid": [0, 2],
            "word": [1],
            "invalid": ["not_int", None],  # Should be skipped
        }
    }
    result = OpenAlexFieldMap.reconstruct_abstract(record)
    assert result == "valid word valid"


def test_reconstruct_abstract_skips_unexpected_data():
    """Verifies that abstract reconstruction is skipped for unexpectedly formatted abstract data."""
    record = {"abstract_inverted_index": {"edge_case": None}}
    result = OpenAlexFieldMap.reconstruct_abstract(record)
    assert result is None


def test_reconstruct_abstract_invalid_type():
    """Verifies that abstract reconstruction returns None for non-dictionary input."""
    record = {"abstract_inverted_index": "not a dict"}
    assert OpenAlexFieldMap.reconstruct_abstract(record) is None


# ==================== DOI Normalization ====================


@pytest.mark.parametrize(
    "record,expected",
    [
        # Standard prefix stripping
        ({"doi": "https://doi.org/10.1234/example"}, "10.1234/example"),
        # Already clean (no prefix)
        ({"doi": "10.1234/example"}, "10.1234/example"),
        # With whitespace
        ({"doi": "  https://doi.org/10.1234/example  "}, "10.1234/example"),
        # Empty after strip
        ({"doi": "https://doi.org/"}, None),
        ({"doi": "   "}, None),
        # None/missing
        ({"doi": None}, None),
        ({}, None),
    ],
)
def test_normalize_doi(record, expected):
    """Tests that DOI normalization strips https://doi.org/ prefix from record DOIs."""
    assert OpenAlexFieldMap.normalize_doi(record) == expected


def test_normalize_doi_non_string():
    """Verifies that DOI normalization returns None for non-string input DOIs."""
    record = {"doi": 12345}
    assert OpenAlexFieldMap.normalize_doi(record) is None


# ==================== Author Extraction ====================


@pytest.mark.parametrize(
    "record,expected",
    [
        # Valid list unchanged
        ({"authors": ["John Doe", "Jane Smith"]}, ["John Doe", "Jane Smith"]),
        # Filters empty strings
        ({"authors": ["John Doe", "", "Jane Smith"]}, ["John Doe", "Jane Smith"]),
        # Filters None values
        ({"authors": ["John Doe", None, "Jane Smith"]}, ["John Doe", "Jane Smith"]),
        # All empty/None → None
        ({"authors": ["", None, ""]}, None),
        # Empty list → None
        ({"authors": []}, None),
        # None → None
        ({"authors": None}, None),
        # Missing key → None
        ({}, None),
        # Single author (string, not list) - as_tuple handles
        ({"authors": "Solo Author"}, ["Solo Author"]),
    ],
)
def test_extract_authors(record, expected):
    """Verifies that author extraction filters empty/None entries."""
    assert OpenAlexFieldMap.extract_authors(record) == expected


def test_extract_authors_whitespace_only():
    """Tests whether author extraction filters whitespace-only entries."""
    # Note: Current implementation uses truthiness, so "  " is truthy
    # This test documents current behavior
    record = {"authors": ["John Doe", "   ", "Jane Smith"]}
    result = OpenAlexFieldMap.extract_authors(record)
    # Whitespace strings are truthy, so they pass the filter
    assert result == ["John Doe", "Jane Smith"]


# ==================== PMID Extraction ====================


@pytest.mark.parametrize(
    "record,expected",
    [
        # Full URL extraction
        ({"pmid": "https://pubmed.ncbi.nlm.nih.gov/29241234"}, "29241234"),
        # With trailing slash
        ({"pmid": "https://pubmed.ncbi.nlm.nih.gov/29241234/"}, "29241234"),
        # Just ID (no prefix)
        ({"pmid": "29241234"}, "29241234"),
        # Empty after strip
        ({"pmid": "https://pubmed.ncbi.nlm.nih.gov/"}, None),
        # None/missing
        ({"pmid": None}, None),
        ({}, None),
    ],
)
def test_extract_pmid(record, expected):
    """Verifies that PMID extraction strips PubMed URL prefixes."""
    assert OpenAlexFieldMap.extract_pmid(record) == expected


def test_extract_pmid_from_nested_ids():
    """Verifies that PMID extraction falls back to the `ids.pmid` path."""
    record = {"ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345678"}}
    assert OpenAlexFieldMap.extract_pmid(record) == "12345678"


def test_extract_pmid_non_string():
    """Verifies that PMID extraction returns None for non-string input."""
    record = {"pmid": 12345}
    assert OpenAlexFieldMap.extract_pmid(record) is None


# ==================== Integration Tests ====================


def test_post_process_open_access_record():
    """Verifies the post-processing step with a basic mocked open access record."""
    record = {
        "provider_name": "openalex",
        "doi": "https://doi.org/10.1371/journal.pone.0123456",
        "title": "Open Access Research Article",
        "authors": ["John Doe", "", "Jane Smith", None],
        "abstract_inverted_index": {
            "This": [0],
            "is": [1],
            "an": [2],
            "abstract": [3],
        },
        "open_access": True,
        "is_retracted": False,
    }
    processed = openalex_field_map._post_process(record)

    assert processed["doi"] == "10.1371/journal.pone.0123456"
    assert processed["abstract"] == "This is an abstract"
    assert processed["authors"] == ["John Doe", "Jane Smith"]
    assert processed["open_access"] is True
    assert processed["is_retracted"] is False


def test_post_process_closed_access_record():
    """Full post-processing of a mock closed access record without abstract."""
    record = {
        "provider_name": "openalex",
        "doi": "https://doi.org/10.1016/j.example.2024.01.001",
        "title": "Subscription Article",
        "authors": ["Single Author"],
        "abstract_inverted_index": None,
        "open_access": False,
    }
    processed = openalex_field_map._post_process(record)

    assert processed["doi"] == "10.1016/j.example.2024.01.001"
    assert processed["abstract"] is None
    assert processed["authors"] == ["Single Author"]
    assert processed["open_access"] is False


def test_post_process_minimal_record():
    """Post-processing handles minimal/empty records gracefully."""
    processed = openalex_field_map._post_process({"provider_name": "openalex"})

    assert processed["provider_name"] == "openalex"
    assert processed["doi"] is None
    assert processed["abstract"] is None
    assert processed["authors"] is None


def test_post_process_none_values():
    """Verifies that post-processing can handle None values gracefully."""
    record = {
        "provider_name": "openalex",
        "doi": None,
        "authors": None,
        "abstract_inverted_index": None,
    }
    processed = openalex_field_map._post_process(record)

    assert processed["doi"] is None
    assert processed["abstract"] is None
    assert processed["authors"] is None


def test_post_process_preserves_api_fields():
    """Tests that API-specific fields pass through post-processing unchanged."""
    record = {
        "provider_name": "openalex",
        "doi": "https://doi.org/10.1234/test",
        "openalex_id": "W1234567890",
        "oa_status": "gold",
        "fwci": 1.5,
        "volume": "42",
        "issue": "3",
    }
    processed = openalex_field_map._post_process(record)

    assert processed["openalex_id"] == "W1234567890"
    assert processed["oa_status"] == "gold"
    assert processed["fwci"] == 1.5
    assert processed["volume"] == "42"
    assert processed["issue"] == "3"


def test_post_process_retracted_article():
    """Verifies that post-processing preserves retraction status."""
    record = {
        "provider_name": "openalex",
        "doi": "https://doi.org/10.1234/retracted",
        "title": "Retracted Article",
        "is_retracted": True,
        "authors": ["Former Author"],
    }
    processed = openalex_field_map._post_process(record)

    assert processed["is_retracted"] is True
    assert processed["doi"] == "10.1234/retracted"


# ==================== Full Normalization Tests ====================


def test_normalize_record_open_access(openalex_sample_open_access_record):
    """Verifies the structure of an open access mock OpenAlex record after normalization."""
    normalized = openalex_field_map.normalize_record(openalex_sample_open_access_record)

    # Core identifiers
    assert normalized["provider_name"] == "openalex"
    assert normalized["record_id"] == "https://openalex.org/W2741809807"
    assert normalized["doi"] == "10.1371/journal.pone.0185809"
    assert normalized["url"] == "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0185809"

    # Bibliographic metadata
    assert normalized["title"] == "The impact of climate change on global biodiversity patterns"
    assert normalized["abstract"] == "Climate change is affecting biodiversity globally."
    assert normalized["authors"] == ["Maria García", "John Smith"]

    # Publication metadata
    assert normalized["journal"] == "PLOS ONE"
    assert normalized["publisher"] == "Public Library of Science"
    assert normalized["year"] == 2023
    assert normalized["date_published"] == "2023-06-15"
    assert normalized["date_created"] == "2023-06-10"

    # Content and classification
    assert "climate change" in normalized["keywords"]
    assert "Ecology" in normalized["subjects"]

    # Metrics
    assert normalized["citation_count"] == 42

    # Access and rights
    assert normalized["open_access"] is True
    assert normalized["license"] == "cc-by"
    assert normalized["is_retracted"] is False

    # Document metadata
    assert normalized["record_type"] == "article"
    assert normalized["language"] == "en"

    # API-specific fields
    assert normalized["oa_status"] == "gold"
    assert normalized["volume"] == "18"
    assert normalized["issue"] == "6"
    assert normalized["fwci"] == 1.23
    assert normalized["references_count"] == 85


def test_normalize_record_closed_access(openalex_sample_closed_access_record):
    """Tests the full normalization of a mock closed access record from an API response."""
    normalized = openalex_field_map.normalize_record(openalex_sample_closed_access_record)

    # Core identifiers
    assert normalized["provider_name"] == "openalex"
    assert normalized["record_id"] == "https://openalex.org/W1234567890"
    assert normalized["doi"] == "10.1016/j.example.2024.01.001"

    # Abstract is None (no inverted index)
    assert normalized["abstract"] is None

    # Single author
    assert normalized["authors"] == ["Jane Doe"]

    # Publication metadata
    assert normalized["journal"] == "Journal of Expensive Research"
    assert normalized["publisher"] == "Elsevier"
    assert normalized["year"] == 2024

    # Access - closed
    assert normalized["open_access"] is False
    assert normalized["oa_status"] == "closed"
    assert normalized["license"] is None


def test_normalize_record_retracted(openalex_sample_retracted_record):
    """Verifies the full normalization of a mock retracted record from an API response."""
    normalized = openalex_field_map.normalize_record(openalex_sample_retracted_record)

    # Core fields
    assert normalized["doi"] == "10.1234/retracted.2020"
    assert "RETRACTED" in normalized["title"]

    # Abstract reconstructed
    assert normalized["abstract"] is not None
    assert "RETRACTED" in normalized["abstract"]

    # Retraction status preserved
    assert normalized["is_retracted"] is True

    # Still marked as OA (license exists)
    assert normalized["open_access"] is True


def test_normalize_record_minimal(openalex_sample_record_minimal):
    """Verifies the full normalization of a minimal mocked record containing required fields only."""
    normalized = openalex_field_map.normalize_record(openalex_sample_record_minimal)

    assert normalized["provider_name"] == "openalex"
    assert normalized["record_id"] == "https://openalex.org/W0000000001"
    assert normalized["title"] == "Minimal Record"
    assert normalized["doi"] is None
    assert normalized["abstract"] is None
    assert normalized["authors"] is None
    assert normalized["year"] is None


def test_normalize_record_batch(
    openalex_sample_open_access_record,
    openalex_sample_closed_access_record,
    openalex_sample_retracted_record,
    openalex_sample_record_minimal,
):
    """Tests the behavior of normalization with three mocked OpenAlex records."""
    records = [
        openalex_sample_open_access_record,
        openalex_sample_closed_access_record,
        openalex_sample_retracted_record,
        openalex_sample_record_minimal,
    ]

    normalized_list = openalex_field_map.normalize_records(records)

    assert len(normalized_list) == len(records)

    # Verify each record normalized correctly
    assert normalized_list[0]["record_id"] == "https://openalex.org/W2741809807"
    assert normalized_list[0]["open_access"] is True
    assert normalized_list[0]["is_retracted"] is False

    assert normalized_list[1]["record_id"] == "https://openalex.org/W1234567890"
    assert normalized_list[1]["open_access"] is False
    assert normalized_list[1]["abstract"] is None

    assert normalized_list[2]["record_id"] == "https://openalex.org/W9999999999"
    assert normalized_list[2]["open_access"] is True
    assert normalized_list[2]["is_retracted"] is True

    assert normalized_list[3]["record_id"] == "https://openalex.org/W0000000001"
    assert normalized_list[3]["open_access"] is None
    assert normalized_list[3]["is_retracted"] is None
