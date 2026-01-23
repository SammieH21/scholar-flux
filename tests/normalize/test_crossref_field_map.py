"""Tests for Crossref field map normalization and post-processing.

This test suite covers:
1. Date extraction (year, date_published, date_created)
2. Author name formatting
3. Open Access resolution from license URLs
4. Journal extraction
5. Abstract extraction and HTML Tag Removal
6. Retraction status detection
7. Integration with real-world record structures

"""

import pytest
from scholar_flux.utils.helpers import BeautifulSoup
from scholar_flux.api.normalization.crossref_field_map import (
    CrossrefFieldMap,
    field_map as crossref_field_map,
)


# ==================== Fixtures ====================


@pytest.fixture
def crossref_raw_record_elsevier():
    """Fixture of a raw, mocked Crossref record from Elsevier with TDM license (before normalization)."""
    return {
        "DOI": "10.1016/0160-7979(78)90159-5",
        "URL": "https://doi.org/10.1016/0160-7979(78)90159-5",
        "title": "Benefits in medical care programs",
        "abstract": "<p>This study examines the impact of medical care programs on...</p><p> Thus we conclude...</p>",
        "created": {"date-parts": [[2002, 10, 9]]},
        "published": {"date-parts": [[1978, 1]]},
        "license": [{"URL": "https://www.elsevier.com/tdm/userlicense/1.0/"}],
        "author": [{"given": "William", "family": "Shonick"}],
        "type": "journal-article",
    }


@pytest.fixture
def crossref_raw_record_cc_by():
    """Fixture for a raw, mocked Crossref record with CC-BY open access license (before normalization)."""
    return {
        "DOI": "10.1371/journal.pone.0123456",
        "published": {"date-parts": [[2024, 6, 15]]},
        "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
        "author": [
            {"given": "John", "family": "Doe"},
            {"given": "Jane", "family": "Smith"},
        ],
    }


@pytest.fixture
def crossref_raw_record_minimal():
    """A minimal raw, mocked Crossref record fixture with only required fields (before normalization)."""
    return {
        "DOI": "10.1234/test",
    }


# ==================== Date Extraction ====================


@pytest.mark.parametrize(
    "record,expected",
    [
        # Standard date-parts arrays
        ([2024, 7, 10], 2024),
        ([2021, 11], 2021),
        ([1998], 1998),
        (2020, 2020),  # Single int (as_tuple wraps)
        (["2023", 5, 15], 2023),  # String coercion
        # Edge cases
        ([], None),
        (None, None),
        ({}, None),
    ],
)
def test_extract_year(record, expected):
    """Verifies that years extracted from date part lists are extracted as integers."""
    record = record if isinstance(record, dict) else {"year": record}
    assert CrossrefFieldMap.extract_year(record) == expected


@pytest.mark.parametrize(
    "date_published,expected",
    [
        ([2024, 12, 18], "2024-12-18"),
        ([2021, 11], "2021-11"),
        ([1998], "1998"),
        ([2022, 6, 2], "2022-06-02"),  # Zero-padding
        (None, None),
    ],
)
def test_extract_date_published(date_published, expected):
    """Tests that the publication date can be successfully extracted and constructed from date parts."""
    record = {"date_published": date_published}
    assert CrossrefFieldMap.extract_date_parts(record, "date_published") == expected


@pytest.mark.parametrize(
    "date_created,expected",
    [
        ([2002, 10, 9], "2002-10-09"),
        ([2007, 10], "2007-10"),
        ([2006], "2006"),
        (None, None),
    ],
)
def test_extract_date_created(date_created, expected):
    """Tests that the date of record creation can be successfully extracted and constructed from date parts."""
    record = {"date_created": date_created}
    assert CrossrefFieldMap.extract_date_parts(record, "date_created") == expected


# ==================== Author Extraction ====================


@pytest.mark.parametrize(
    "author_list,expected",
    [
        # Single author (dict, not list) - Crossref quirk
        ({"given": "William", "family": "Shonick"}, ["William Shonick"]),
        # Multiple authors
        ([{"given": "John", "family": "Doe"}, {"given": "Jane", "family": "Smith"}], ["John Doe", "Jane Smith"]),
        # Initials preserved
        ([{"given": "C. S.", "family": "Rundall"}], ["C. S. Rundall"]),
        # Family name only
        ([{"family": "Anonymous"}], ["Anonymous"]),
        # Mixed completeness
        ([{"given": "John", "family": "Smith"}, {"family": "Solo"}], ["John Smith", "Solo"]),
        # Unicode names
        (
            [
                {"given": "José", "family": "García"},
                {"given": "François", "family": "Müller"},
                {"given": "幸", "family": "泉"},
            ],
            ["José García", "François Müller", "幸 泉"],
        ),
        # Filters invalid and empty family names
        (
            ["string_not_dict", {"given": "John", "family": ""}, {"given": "Valid", "family": "Author"}],
            ["Valid Author"],
        ),
        # Empty/None cases
        ([], None),
        (None, None),
    ],
)
def test_extract_authors(author_list, expected):
    """Verifies that author names are the extracted `author_list` field, including unicode and invalid cases."""
    record = {"author_list": author_list}
    assert CrossrefFieldMap.extract_authors(record) == expected


# ==================== Open Access Resolution ====================


@pytest.mark.parametrize(
    "license_urls,expected",
    [
        # BOAI-Compliant (`True`)
        (["https://creativecommons.org/licenses/by/4.0/"], True),
        (["https://creativecommons.org/licenses/by-sa/4.0/"], True),
        (["https://creativecommons.org/publicdomain/zero/1.0/"], True),
        # Restricted (`False`)
        (["https://www.elsevier.com/tdm/userlicense/1.0/"], False),
        (["https://doi.wiley.com/10.1002/tdm_license_1.1"], False),
        (["https://www.springer.com/tdm"], False),
        (["https://www.cambridge.org/core/terms"], False),
        # Debatable (`None`)
        (["https://creativecommons.org/licenses/by-nc/4.0/"], None),
        (["https://creativecommons.org/licenses/by-nd/4.0/"], None),
        (["https://creativecommons.org/licenses/by-nc-nd/4.0/"], None),
        # Mixed (`True` wins)
        (
            [
                "https://creativecommons.org/licenses/by/4.0/",
                "https://www.elsevier.com/tdm/userlicense/1.0/",
            ],
            True,
        ),
        # Multiple restricted (`False`)
        (
            [
                "https://www.elsevier.com/tdm/userlicense/1.0/",
                "https://www.cambridge.org/core/terms",
            ],
            False,
        ),
        # Edge cases
        (["https://example.com/unknown-license"], None),
        ([], None),
        (None, None),
    ],
)
def test_resolve_open_access(license_urls, expected):
    """Verifies that open access statuses can be resolved from license URLs."""
    record = {"license": license_urls}
    assert CrossrefFieldMap.resolve_open_access(record) == expected


# ==================== Journal Extraction ====================


@pytest.mark.parametrize(
    "journal_input,expected",
    [
        ("Journal of Scientific Computation", "Journal of Scientific Computation"),
        (["Journal A", "Journal B"], "Journal A; Journal B"),
        (None, None),
        ({"invalid": "type"}, None),
        (123, None),
    ],
)
def test_extract_journal(journal_input, expected):
    """Tests that journal extraction handles strings, lists, and invalid types."""
    record = {"journal": journal_input}
    assert CrossrefFieldMap.extract_journal(record) == expected


# ==================== Retraction Status ====================


@pytest.mark.parametrize(
    "updated_by_list,expected",
    [
        # Retraction/withdrawal detected
        ({"type": "retraction"}, True),
        ({"type": "withdrawal"}, True),
        ({"type": "RETRACTION"}, True),  # Case insensitive
        # Not retracted
        ({"type": "correction"}, None),
        ({"type": 123}, None),  # Invalid type
        ([], None),
        (None, None),
        # Multiple updates - finds retraction
        ([{"type": "correction"}, {"type": "retraction"}], True),
    ],
)
def test_check_retraction(updated_by_list, expected):
    """Verifies that retraction is detected only if `retraction` exists in the `updated_by_list`."""
    record = (
        updated_by_list
        if isinstance(updated_by_list, dict) and "type" not in updated_by_list
        else {"updated_by_list": updated_by_list}
    )
    assert CrossrefFieldMap.check_retraction(record) is expected


# ==================== Abstract Extraction ====================


def test_abstract_extraction(crossref_raw_record_elsevier):
    """Verifies that tags are extracted as intended when BeautifulSoup is installed."""
    if BeautifulSoup is None:
        pytest.skip("BeautifulSoup is not installed, skipping check for tag extraction...")
    normalized_record = crossref_field_map._post_process(crossref_raw_record_elsevier)
    parsed_abstract = normalized_record["abstract"]
    assert parsed_abstract == "This study examines the impact of medical care programs on... Thus we conclude..."

    parsed_abstract = CrossrefFieldMap.extract_abstract(crossref_raw_record_elsevier, separator=" |", strip_html=True)
    assert parsed_abstract == "This study examines the impact of medical care programs on... | Thus we conclude..."

    parsed_abstract = CrossrefFieldMap.extract_abstract(
        crossref_raw_record_elsevier, separator=";", strip=False, strip_html=True
    )
    assert parsed_abstract == "This study examines the impact of medical care programs on...; Thus we conclude..."


# ==================== Integration Tests ====================


def test_post_process_elsevier_record():
    """Tests the post-processing step against a mock journal article after basic normalization."""
    record = {
        "provider_name": "crossref",
        "doi": "10.1016/0160-7979(78)90159-5",
        "url": "https://doi.org/10.1016/0160-7979(78)90159-5",
        "title": "Benefits in medical care programs",
        "year": [2002, 10, 9],
        "date_published": [1978, 1],
        "date_created": [2002, 10, 9],
        "license": "https://www.elsevier.com/tdm/userlicense/1.0/",
        "author_list": {"given": "William", "family": "Shonick"},
        "type": "journal-article",
    }
    processed = crossref_field_map._post_process(record)

    assert processed["doi"] == "10.1016/0160-7979(78)90159-5"
    assert processed["authors"] == ["William Shonick"]
    assert processed["year"] == 2002
    assert processed["url"] == "https://doi.org/10.1016/0160-7979(78)90159-5"
    assert processed["date_published"] == "1978-01"
    assert processed["date_created"] == "2002-10-09"
    assert processed["open_access"] is False
    assert processed["license"] == record["license"]
    assert processed["type"] == "journal-article"  # API field preserved


def test_sample_creative_commons_record_normalization_post_processing_step():
    """Tests the post-processing step against a mock creative commons record after basic normalization."""

    record = {
        "provider_name": "crossref",
        "doi": "10.1371/journal.pone.0123456",
        "year": [2024, 6, 15],
        "date_published": [2024, 6, 15],
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "author_list": [
            {"given": "John", "family": "Doe"},
            {"given": "Jane", "family": "Smith"},
        ],
    }

    processed = crossref_field_map._post_process(record)

    assert processed["doi"] == "10.1371/journal.pone.0123456"
    assert processed["authors"] == ["John Doe", "Jane Smith"]
    assert processed["title"] is None
    assert processed["year"] == 2024
    assert processed["date_published"] == "2024-06-15"
    assert processed["date_created"] is None
    assert processed["license"] == record["license"]
    assert processed["open_access"] is True


def test_post_process_minimal_record():
    """Verifies that the Crossref post-processing step handles minimal/empty records gracefully."""
    record = {
        "provider_name": "crossref",
    }
    processed = crossref_field_map._post_process(record)

    assert processed["provider_name"] == "crossref"
    assert processed["authors"] is None
    assert processed["year"] is None
    assert processed["open_access"] is None


# ==================== Full Normalization Tests ====================


def test_normalize_record_elsevier(crossref_raw_record_elsevier):
    """Tests the full normalization of a mock Elsevier TDM record."""
    normalized = crossref_field_map.normalize_record(crossref_raw_record_elsevier)

    # Core identifiers
    assert normalized["provider_name"] == "crossref"
    assert normalized["doi"] == "10.1016/0160-7979(78)90159-5"
    assert normalized["url"] == "https://doi.org/10.1016/0160-7979(78)90159-5"
    expected = "This study examines the impact of medical care programs on..."
    assert expected in normalized["abstract"]

    # Bibliographic metadata
    assert normalized["title"] == "Benefits in medical care programs"
    assert normalized["authors"] == ["William Shonick"]

    # Publication metadata
    assert normalized["year"] == 2002
    assert normalized["date_published"] == "1978-01"
    assert normalized["date_created"] == "2002-10-09"

    # Access
    assert normalized["open_access"] is False
    assert normalized["license"] == "https://www.elsevier.com/tdm/userlicense/1.0/"

    # Document metadata
    assert normalized["record_type"] == "journal-article"


def test_normalize_record_cc_by(crossref_raw_record_cc_by):
    """Tests the full normalization of a mock, CC-BY open access record."""
    normalized = crossref_field_map.normalize_record(crossref_raw_record_cc_by)

    # Core identifiers
    assert normalized["provider_name"] == "crossref"
    assert normalized["doi"] == "10.1371/journal.pone.0123456"

    # Bibliographic metadata
    assert normalized["authors"] == ["John Doe", "Jane Smith"]
    assert normalized["abstract"] is None

    # Publication metadata
    assert normalized["year"] == 2024
    assert normalized["date_published"] == "2024-06-15"

    # Access
    assert normalized["open_access"] is True
    assert normalized["license"] == "https://creativecommons.org/licenses/by/4.0/"


def test_normalize_record_minimal(crossref_raw_record_minimal):
    """Tests the full normalization of a minimal, mocked Crossref record."""
    normalized = crossref_field_map.normalize_record(crossref_raw_record_minimal)

    # Only provider name and DOI should be present
    assert normalized["provider_name"] == "crossref"
    assert normalized["doi"] == "10.1234/test"
    assert normalized["authors"] is None
    assert normalized["year"] is None
    assert normalized["open_access"] is None


def test_normalize_record_batch(
    crossref_raw_record_elsevier,
    crossref_raw_record_cc_by,
    crossref_raw_record_minimal,
):
    """Tests the batch normalization of three mocked Crossref records."""
    records = [
        crossref_raw_record_elsevier,
        crossref_raw_record_cc_by,
        crossref_raw_record_minimal,
    ]

    normalized_list = crossref_field_map.normalize_records(records)

    assert len(normalized_list) == len(records)

    # Verify each record was processed correctly
    assert normalized_list[0]["open_access"] is False  # Elsevier
    assert normalized_list[1]["open_access"] is True  # CC-BY
    assert normalized_list[2]["open_access"] is None  # Minimal

    # Verify IDs
    assert normalized_list[0]["doi"] == "10.1016/0160-7979(78)90159-5"
    assert normalized_list[1]["doi"] == "10.1371/journal.pone.0123456"
    assert normalized_list[2]["doi"] == "10.1234/test"
