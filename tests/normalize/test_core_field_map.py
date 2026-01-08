"""Tests for Core field map normalization and post-processing.

This test suite covers:
1. Year extraction from date strings
2. Record ID extraction and coercion
3. Journal extraction (single and list formats)
4. Open access defaults (always True for Core)
5. Cross-reference identifier extraction (arXiv, PMID, MAG)
6. Integration with real record structures

"""

import pytest
from scholar_flux.api.normalization.core_field_map import (
    CoreFieldMap,
    field_map as core_field_map,
)


@pytest.fixture
def core_sample_record_standard():
    """Fixture of a mocked API response from the Core API."""
    return {
        "id": 12345678,
        "doi": "10.1371/journal.pone.0123456",
        "title": "Impact of Climate Change on Biodiversity",
        "abstract": "This comprehensive study examines the effects of climate change on global biodiversity patterns.",
        "authors": [
            {"name": "Maria García"},
            {"name": "John Smith"},
            {"name": "Alice Johnson"},
        ],
        "journals": {"title": ["PLOS ONE"]},
        "publisher": "Public Library of Science",
        "yearPublished": 2023,
        "publishedDate": "2023-06-15",
        "createdDate": "2023-06-10",
        "fieldOfStudy": ["Environmental Science", "Ecology", "Climate Change"],
        "fullText": "Full article text here...",
        "citationCount": 42,
        "documentType": "article",
        "language": {"name": "English"},
        "downloadUrl": "https://core.ac.uk/download/pdf/12345678.pdf",
        # Cross-reference identifiers
        "arxivId": "1012.4340",
        "pubmedId": "98765432",
        "magId": "2056403249",
    }


@pytest.fixture
def core_sample_record_thesis():
    """Fixture of a thesis record from a mocked API response from the Core API."""
    return {
        "id": 98765432,
        "doi": None,
        "title": "Machine Learning Approaches to Natural Language Processing",
        "abstract": "This doctoral thesis explores novel machine learning techniques for NLP tasks.",
        "authors": [{"name": "PhD Candidate"}],
        "journals": {"title": None},
        "publisher": "University Repository",
        "yearPublished": 2024,
        "publishedDate": "2024-03-01",
        "createdDate": "2024-02-15",
        "fieldOfStudy": ["Computer Science", "Machine Learning", "NLP"],
        "fullText": "Thesis content...",
        "citationCount": 0,
        "documentType": "thesis",
        "language": {"name": "English"},
        "downloadUrl": "https://core.ac.uk/download/pdf/98765432.pdf",
        "arxivId": "None",
        "pubmedId": "None",
        "magId": "None",
    }


@pytest.fixture
def core_sample_record_minimal():
    """A minimal fixture containing a record from a mocked Core API response with basic fields only."""
    return {
        "id": 11111111,
        "title": "Minimal Core Record",
        "authors": [{"name": "Anonymous Author"}],
        "yearPublished": 2020,
    }


# ==================== Year Extraction ====================


@pytest.mark.parametrize(
    "year,expected",
    [
        # ISO date strings
        ("2023-03-17", 2023),
        ("2025-12-01T10:30:00Z", 2025),
        ("2022-11", 2022),
        ("2019", 2019),
        # Edge cases
        ("", None),
        (None, None),
        ({}, None),
    ],
)
def test_extract_year(year, expected):
    """Verifies both common and edge cases involving year extraction from ISO date strings."""
    record = {"year": year} if not isinstance(year, dict) else year
    assert CoreFieldMap.extract_year(record) == expected


# ==================== ID Extraction ====================


@pytest.mark.parametrize(
    "id,expected",
    [
        # String IDs
        ("12345678", "12345678"),
        ("core:oai:example.org:12345", "core:oai:example.org:12345"),
        # Integer ID (should be coerced to string)
        (12345678, "12345678"),
        # Edge cases
        ("", None),
        (None, None),
        ({}, None),
    ],
)
def test_extract_id(id, expected):
    """Verifies both common and edge cases involving the extraction of record IDs."""
    record = {"record_id": id} if not isinstance(id, dict) else id
    assert CoreFieldMap.extract_id(record) == expected


# ==================== Cross-Reference Identifier Extraction ====================


####### arXiv ID extraction ########


@pytest.mark.parametrize(
    "arxiv_id,expected",
    [
        ("1012.4340", "1012.4340"),
        ("2301.12345", "2301.12345"),
        ("hep-th/9901001", "hep-th/9901001"),
        ("None", None),  # Core's None string
        (None, None),
        ({}, None),
    ],
)
def test_extract_arxiv_id(arxiv_id, expected):
    """Verifies that `extract_arxiv_id` can correctly extract arXiv IDs from Core records when available."""
    record = {"arxiv_id": arxiv_id} if not isinstance(arxiv_id, dict) else arxiv_id
    assert CoreFieldMap.extract_arxiv_id(record) == expected


###### PubMed ID Extraction ########


@pytest.mark.parametrize(
    "pmid,pubmed_id,expected",
    [
        ("12345678", None, "12345678"),
        ("9876543", "22222222", "9876543"),  # PMID should be preferred
        (None, "87654321", "87654321"),  # "pubmed_id" is used as a fallback when `PMID` is not available
        ("None", None, None),  # Core's None string should be auto-converted into None
        (None, None, None),
        ({}, None, None),
    ],
)
def test_extract_pmid(pmid, pubmed_id, expected):
    """Verifies that `extract_pmid` can reliably extract PubMed IDs while handling different Core record formats."""
    record = {"pmid": pmid, "pubmed_id": pubmed_id} if not isinstance(pmid, dict) else pmid
    assert CoreFieldMap.extract_pmid(record) == expected


@pytest.mark.parametrize(
    "mag_id,expected",
    [
        ("2056403249", "2056403249"),
        ("1234567890", "1234567890"),
        ("None", None),  # Core's None string
        (None, None),
        ({}, None),
    ],
)
def test_extract_mag_id(mag_id, expected):
    """Verifies that `extract_mag_id` can reliably retrieve Microsoft Academic Graph IDs from Core records."""
    record = {"mag_id": mag_id} if not isinstance(mag_id, dict) else mag_id
    assert CoreFieldMap.extract_mag_id(record) == expected


# ==================== Journal Extraction ====================


@pytest.mark.parametrize(
    "record,expected",
    [
        # Single journal as string
        ("Nature", "Nature"),
        # Single journal nested within a list
        (["Solo Journal"], "Solo Journal"),
        # List of journals - joined with semicolon
        (["Nature", "Science"], "Nature; Science"),
        # Tuple of journals
        (("PLOS ONE", "BMC Biology"), "PLOS ONE; BMC Biology"),
        # List with empty/None values filtered out
        (["Nature", "", "Science"], "Nature; Science"),
        (["Nature", None, "Science"], "Nature; Science"),
        # All empty/None values
        (["", None, ""], None),
        # Edge cases
        ("", None),
        (12345, None),  # (incorrect types)
        ([], None),
        (None, None),
        ({}, None),
    ],
)
def test_extract_journal(record, expected):
    """Verifies that `extract_journal` can handle several nested `journal` field formats gracefully when populated."""
    record = record if isinstance(record, dict) else {"journal": record}
    assert CoreFieldMap.extract_journal(record) == expected


# ==================== Open Access (Default True) ====================


@pytest.mark.parametrize("record", ({"provider_name": "core"}, {"provider_name": "core", "open_access": False}, {}))
def test_open_access_is_always_true(record):
    """Core is primarily open access: the `open_access` field should always be true, regardless of inputs."""
    processed = core_field_map._post_process(record)
    # Since the field_map has open_access=None, default applies
    assert processed["open_access"] is True


# ==================== Edge Cases ====================


def test_normalize_record_single_author():
    """Tests that Normalization handles single author dict (not in list)."""
    record = {
        "id": "00001111",
        "title": "Solo Research",
        "authors": {"name": "Solo Researcher"},
        "yearPublished": 2024,
    }
    normalized_record = core_field_map.normalize_record(record)

    assert normalized_record["authors"] is not None
    assert "Solo Researcher" in str(normalized_record["authors"])


def test_normalize_record_empty_author_list():
    """Verifies that an empty list of author names resolves to None on extraction."""
    record = {
        "id": "00002222",
        "title": "Anonymous Submission",
        "authors": [],
        "yearPublished": 2024,
    }
    normalized_record = core_field_map.normalize_record(record)
    assert normalized_record["authors"] is None or normalized_record["authors"] == []


def test_normalize_record_numeric_year():
    """When encountering a numeric year (as opposed to a string), it should be extracted and returned as is."""
    record = {
        "id": "00003333",
        "title": "Numeric Year Record",
        "yearPublished": 2024,
    }
    normalized_record = core_field_map.normalize_record(record)
    assert normalized_record["year"] == 2024


def test_normalize_record_null_nested_fields():
    """Verifies that nested fields containing null values are handled gracefully during field extraction."""
    record = {
        "id": "00004444",
        "title": "Null Fields Record",
        "journals": None,
        "language": None,
        "authors": None,
    }
    normalized_record = core_field_map.normalize_record(record)

    assert normalized_record["record_id"] == "00004444"
    assert normalized_record["journal"] is None
    assert normalized_record["language"] is None
    assert normalized_record["authors"] is None


def test_normalize_record_empty_field_of_study():
    """Verifies that `keywords` is left as None after normalization when `fieldOfStudy` is an empty list."""
    record = {
        "id": "00005555",
        "title": "No Subjects Record",
        "fieldOfStudy": [],
    }
    normalized_record = core_field_map.normalize_record(record)
    assert normalized_record["keywords"] is None or normalized_record["keywords"] == []


# ==================== Post-Processing Integration ====================


def test_post_process_standard_record():
    """Verifies that normalized Core records are post-processed as intended to produce the final processed record."""
    record = {
        "provider_name": "core",
        "record_id": "12345678",
        "arxiv_id": "1012.4340",
        "pmid": "None",
        "mag_id": "2056403249",
        "title": "Open Access Research Article",
        "date": "2024-06-15",
        "year": "2024-06-15",
        "authors": ["John Doe", "Jane Smith"],
        "abstract": "This study examines...",
        "journal": ["Primary Journal", "Secondary Source"],
        "doi": "10.1234/example.2024",
    }
    processed = core_field_map._post_process(record)

    assert processed["record_id"] == "12345678"

    # extracted from `year`
    assert processed["date"] == "2024-06-15"
    assert processed["year"] == 2024
    assert processed["open_access"] is True
    assert processed["journal"] == "Primary Journal; Secondary Source"
    assert processed["authors"] == ["John Doe", "Jane Smith"]
    assert processed["arxiv_id"] == "1012.4340"
    assert processed["pmid"] is None  # "None" -> None
    assert processed["mag_id"] == "2056403249"


# ==================== Full Normalization Tests ====================


def test_normalize_record_standard(core_sample_record_standard):
    """Verifies that the normalization of the standard Core sample record produces the expected results."""
    normalized_record = core_field_map.normalize_record(core_sample_record_standard)

    # Core identifiers
    assert normalized_record["provider_name"] == "core"
    assert normalized_record["record_id"] == "12345678"
    assert normalized_record["doi"] == "10.1371/journal.pone.0123456"
    assert normalized_record["url"] == "https://core.ac.uk/download/pdf/12345678.pdf"

    # Bibliographic metadata
    assert normalized_record["title"] == "Impact of Climate Change on Biodiversity"
    assert "comprehensive study" in normalized_record["abstract"]
    assert normalized_record["authors"] == ["Maria García", "John Smith", "Alice Johnson"]

    # Publication metadata
    assert normalized_record["journal"] == "PLOS ONE"
    assert normalized_record["publisher"] == "Public Library of Science"
    assert normalized_record["year"] == 2023
    assert normalized_record["date_published"] == "2023-06-15"
    assert normalized_record["date_created"] == "2023-06-10"

    # Content classification (mapped from fieldOfStudy)
    assert "Environmental Science" in normalized_record["keywords"]
    assert normalized_record["subjects"] == normalized_record["keywords"]

    # Metrics
    assert normalized_record["citation_count"] == 42

    # Access - Core defaults to open access
    assert normalized_record["open_access"] is True
    assert normalized_record["license"] is None

    # Document metadata
    assert normalized_record["record_type"] == "article"
    assert normalized_record["language"] == "English"

    # Cross-reference identifiers
    assert normalized_record["arxiv_id"] == "1012.4340"
    assert normalized_record["pmid"] == "98765432"
    assert normalized_record["mag_id"] == "2056403249"


def test_normalize_record_thesis(core_sample_record_thesis):
    """Verifies that the normalization of the Core sample thesis produces the expected results."""
    normalized_record = core_field_map.normalize_record(core_sample_record_thesis)

    # Core identifiers
    assert normalized_record["record_id"] == "98765432"
    assert normalized_record["doi"] is None

    # Bibliographic
    assert "Machine Learning" in normalized_record["title"]
    assert normalized_record["authors"] == ["PhD Candidate"]

    # Publication metadata
    assert normalized_record["journal"] is None
    assert normalized_record["publisher"] == "University Repository"
    assert normalized_record["year"] == 2024

    # Document type
    assert normalized_record["record_type"] == "thesis"

    # Still open access
    assert normalized_record["open_access"] is True

    # Cross-reference identifiers (all None for thesis)
    assert normalized_record["arxiv_id"] is None
    assert normalized_record["pmid"] is None
    assert normalized_record["mag_id"] is None


def test_normalize_record_minimal(core_sample_record_minimal):
    """Verifies that the normalization of minimal Core records produce the expected results, ignoring missing fields."""
    normalized_record = core_field_map.normalize_record(core_sample_record_minimal)

    assert normalized_record["provider_name"] == "core"
    assert normalized_record["record_id"] == "11111111"
    assert normalized_record["title"] == "Minimal Core Record"
    assert normalized_record["year"] == 2020
    assert normalized_record["open_access"] is True

    # Missing fields should be None
    assert normalized_record["doi"] is None
    assert normalized_record["abstract"] is None
    assert normalized_record["journal"] is None
    assert normalized_record["citation_count"] is None
    assert normalized_record["arxiv_id"] is None
    assert normalized_record["pmid"] is None
    assert normalized_record["mag_id"] is None


def test_normalize_record_batch(
    core_sample_record_standard,
    core_sample_record_thesis,
    core_sample_record_minimal,
):
    """Verifies the normalization of sample records of different types in batch with `normalize_records`."""
    records = [
        core_sample_record_standard,
        core_sample_record_thesis,
        core_sample_record_minimal,
    ]

    normalized_list = core_field_map.normalize_records(records)

    assert len(normalized_list) == len(records)

    # All Core records are open access
    assert all(n["open_access"] is True for n in normalized_list)

    # IDs should be extracted in order
    assert normalized_list[0]["record_id"] == str(core_sample_record_standard["id"]) == "12345678"
    assert normalized_list[1]["record_id"] == str(core_sample_record_thesis["id"]) == "98765432"
    assert normalized_list[2]["record_id"] == str(core_sample_record_minimal["id"]) == "11111111"

    # Document types should be extracted and retained under `record_type`
    assert normalized_list[0]["record_type"] == "article"
    assert normalized_list[1]["record_type"] == "thesis"
    assert normalized_list[2]["record_type"] is None
