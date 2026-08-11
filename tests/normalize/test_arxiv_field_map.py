"""Tests for arXiv field map normalization and post-processing.

This test suite covers:
1. Year extraction from ISO date strings
2. arXiv ID extraction from URLs
3. Open access (always True)
4. Integration with real record structures

"""

import pytest

from scholar_flux.api.normalization.arxiv_field_map import (
    ArXivFieldMap,
)
from scholar_flux.api.normalization.arxiv_field_map import (
    field_map as arxiv_field_map,
)


@pytest.fixture
def arxiv_sample_record_modern():
    """Fixture containing a mock arXiv API response for modern record formats (post-2007)."""
    return {
        "id": "http://arxiv.org/abs/2499.12345v2",
        "title": "Deep Learning for Natural Language Processing: A Comprehensive Survey",
        "summary": (
            "This survey provides a comprehensive overview of deep learning techniques..."
            "attention mechanisms, and recent advances in large language models."
        ),
        "published": "2024-01-15T00:00:00Z",
        "updated": "2024-02-20T12:30:00Z",
        "author": [
            {"name": "Alice Johnson"},
            {"name": "Bob Williams"},
            {"name": "Carol Davis"},
        ],
        "category": [
            {"@term": "cs.CL", "@scheme": "http://arxiv.org/schemas/atom"},
            {"@term": "cs.AI", "@scheme": "http://arxiv.org/schemas/atom"},
            {"@term": "cs.LG", "@scheme": "http://arxiv.org/schemas/atom"},
        ],
        "arxiv:primary_category": {"@term": "cs.CL"},
        "arxiv:doi": "10.48550/arXiv.2499.12345",
        "arxiv:journal_ref": None,
        "arxiv:comment": "45 pages, 12 figures, accepted at ACL 2024",
        "link": [
            {"@href": "http://arxiv.org/abs/2499.12345v2", "@rel": "alternate", "@type": "text/html"},
            {"@href": "http://arxiv.org/pdf/2499.12345v2", "@rel": "related", "@type": "application/pdf"},
        ],
        "rights": "http://creativecommons.org/licenses/by/4.0/",
    }


@pytest.fixture
def arxiv_sample_record_legacy():
    """Fixture containing a mock arXiv API response for legacy record formats (pre-2007)."""
    return {
        "id": "http://arxiv.org/abs/hep-th/9711200v3",
        "title": "The Large N Limit of Superconformal Field Theories and Supergravity",
        "summary": "We show that the large N limit of certain conformal field theories "
        "in various dimensions include in their Hilbert space a sector describing "
        "supergravity on the product of Anti-deSitter spacetimes.",
        "published": "1997-11-27T00:00:00Z",
        "updated": "1998-01-22T00:00:00Z",
        "author": [
            {"name": "Juan Maldacena"},
        ],
        "category": {"@term": "hep-th", "@scheme": "http://arxiv.org/schemas/atom"},
        "arxiv:primary_category": {"@term": "hep-th"},
        "arxiv:doi": "10.1023/A:1026654312961",
        "arxiv:journal_ref": "Adv.Theor.Math.Phys. 2 (1998) 231-252",
        "arxiv:comment": "20 pages, harvmac, v2,v3: minor corrections",
        "link": [
            {"@href": "http://arxiv.org/abs/hep-th/9711200v3", "@type": "text/html"},
            {"@href": "http://arxiv.org/pdf/hep-th/9711200v3", "@type": "application/pdf"},
        ],
        "rights": "http://arxiv.org/licenses/assumed-1991-2003/",
    }


# ==================== Year Extraction ====================


@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("2024-03-15T10:30:00Z", 2024),
        ("2023-12-01", 2023),
        ("2021-01", 2021),
        ("2020", 2020),
        ("", None),
        (None, None),
        ({}, None),
    ],
)
def test_extract_year(input_value, expected):
    """Verifies both common and edge cases involving year extraction from ISO date strings."""
    # ArXivFieldMap expects a dict with 'year'
    record = input_value if isinstance(input_value, dict) else {"year": input_value}
    assert ArXivFieldMap.extract_year(record) == expected


# ==================== ID Extraction ====================


@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("http://arxiv.org/abs/2499.12345", "2499.12345"),
        ("https://arxiv.org/abs/hep-th/9901001", "hep-th/9901001"),
        ("2499.12345", "2499.12345"),
        ("hep-th/9901001", "hep-th/9901001"),
        ("", None),
        (None, None),
        ({}, None),
    ],
)
def test_extract_url_id(input_value, expected):
    """Verifies that the arXiv ID extraction normalization step strips the arXiv URL prefix and leaves the ID intact."""
    record = input_value if isinstance(input_value, dict) else {"id": input_value}
    assert ArXivFieldMap.extract_url_id(record, field="id", strip_prefix="https?://arxiv.org/abs/") == expected


# ==================== PDF URL Extraction ====================


@pytest.mark.parametrize(
    "url_list,expected",
    [
        (
            [
                {"@href": "https://arxiv.org/abs/2499.12345", "@type": "text/html"},
                {"@href": "https://arxiv.org/pdf/2499.12345", "@type": "application/pdf"},
            ],
            "https://arxiv.org/pdf/2499.12345",
        ),
        (
            [
                {"@href": "https://arxiv.org/pdf/2499.12345", "@type": "application/pdf"},
                {"@href": "https://arxiv.org/abs/2499.12345", "@type": "text/html"},
            ],
            "https://arxiv.org/pdf/2499.12345",
        ),
        (
            [
                {"@href": "https://arxiv.org/abs/2499.12345", "@type": "text/html"},
            ],
            None,
        ),
        ([], None),
        (None, None),
        ({}, None),
    ],
)
def test_extract_pdf_url(url_list, expected):
    """Verifies that PDF URL extraction filters links by @type='application/pdf'."""
    record = {"url_list": url_list}
    assert ArXivFieldMap.extract_pdf_url(record) == expected


# ==================== Record Type Inference ====================


@pytest.mark.parametrize(
    "journal,comment,expected",
    [
        # Journal field takes precedence
        ("Journal of Machine Learning Research 25 (2024)", None, "journal-article"),
        ("International Journal of AI 12, 100 (2023)", "10 pages", "journal-article"),
        ("Sci Rep 14, 1411 (2024)", None, "journal-article"),
        # Book chapters
        ("In A. Smith (Ed.) Handbook of ML", None, "book-chapter"),
        ("In B. Jones & C. Lee (Eds.) AI Methods", "chapter 5", "book-chapter"),
        # Proceedings from journal field
        ("Proceedings of ICML 2024", None, "proceedings-article"),
        ("Workshop on Neural Networks 2023", None, "proceedings-article"),
        # Comment field fallback (no journal)
        (None, "accepted at NeurIPS 2024", "proceedings-article"),
        (None, "accepted at acl2023", "proceedings-article"),
        (None, "conference paper", "proceedings-article"),
        (None, "accepted by Journal of AI", "accepted"),
        (None, "to appear in Nature", "accepted"),
        (None, "submitted to ICML", "submitted"),
        (None, "under review", "submitted"),
        # Default cases
        (None, "10 pages, 5 figures", "preprint"),
        (None, None, "preprint"),
        ("", "", "preprint"),
    ],
)
def test_extract_record_type(journal, comment, expected):
    """Verifies record type inference from journal and comment fields."""
    record = {"journal": journal, "comment": comment}
    assert ArXivFieldMap.extract_record_type(record) == expected


# ==================== Open Access ====================


def test_open_access_always_true():
    """ArXiv records should always be marked as open access regardless of input."""
    record = {"provider_name": "arxiv", "open_access": False}
    processed = arxiv_field_map._post_process(record)
    assert processed["open_access"] is True


# ==================== Author Extraction ====================


def test_normalize_record_single_author():
    """Verifies that author fields with a single entry is handled gracefully."""
    record = {
        "id": "http://arxiv.org/abs/2499.00001",
        "title": "Research Performed Solo",
        "summary": "Research by one author.",
        "published": "2024-01-01",
        "author": {"name": "Solo Researcher"},  # Single dict, not list
    }
    normalized = arxiv_field_map.normalize_record(record)

    # Should handle single author gracefully
    assert normalized["authors"] == ["Solo Researcher"]


def test_normalize_record_empty_author_list():
    """Verifies that author fields consisting of empty lists are handled gracefully."""
    record = {
        "id": "http://arxiv.org/abs/2499.00002",
        "title": "Anonymous Submission",
        "summary": "Double-blind submission.",
        "published": "2024-01-01",
        "author": [],
    }
    normalized = arxiv_field_map.normalize_record(record)
    # Empty list should result in None
    assert normalized["authors"] is None


# ==================== Post-Processing Integration ====================


def test_post_process_standard_record():
    """Verifies that the post-processing step for arXiv records correctly extracts fields requiring post-processing."""
    record = {
        "provider_name": "arxiv",
        "record_id": "http://arxiv.org/abs/2499.12345",
        "title": "Advances in Machine Learning",
        "year": "2024-01-15T00:00:00Z",
        "authors": ["John Doe", "Jane Smith"],
        "abstract": "We present novel approaches...",
        "license": "http://creativecommons.org/licenses/by/4.0/",
        "url_list": [
            {"@href": "http://arxiv.org/abs/2499.12345", "@type": "text/html"},
            {"@href": "http://arxiv.org/pdf/2499.12345", "@type": "application/pdf"},
        ],
    }
    processed = arxiv_field_map._post_process(record)

    assert processed["record_id"] == "2499.12345"
    assert processed["year"] == 2024
    assert processed["open_access"] is True
    assert processed["pdf_url"] == "http://arxiv.org/pdf/2499.12345"
    assert processed["title"] == "Advances in Machine Learning"
    assert processed["authors"] == ["John Doe", "Jane Smith"]


def test_post_process_minimal_record():
    """Verifies that post-processing handles minimal record gracefully."""
    processed = arxiv_field_map._post_process({"provider_name": "arxiv"})

    assert processed["provider_name"] == "arxiv"
    assert processed["record_id"] is None
    assert processed["year"] is None
    assert processed["pdf_url"] is None
    assert processed["open_access"] is True


# ==================== Full Normalization Tests ====================


def test_normalize_record_modern_format(arxiv_sample_record_modern):
    """Full normalization of modern arXiv record (post-2007 ID format)."""
    normalized = arxiv_field_map.normalize_record(arxiv_sample_record_modern)

    # Core identifiers
    assert normalized["provider_name"] == "arxiv"
    assert normalized["record_id"] == "2499.12345v2"
    assert normalized["url"] == "http://arxiv.org/abs/2499.12345v2"
    assert normalized["doi"] == "10.48550/arXiv.2499.12345"

    # Bibliographic metadata
    assert normalized["title"] == "Deep Learning for Natural Language Processing: A Comprehensive Survey"
    assert "comprehensive overview" in normalized["abstract"]
    assert normalized["authors"] == ["Alice Johnson", "Bob Williams", "Carol Davis"]

    # Publication metadata
    assert normalized["year"] == 2024
    assert normalized["date_published"] == "2024-01-15"
    assert normalized["record_type"] == "proceedings-article"

    # Content classification
    assert normalized["subjects"] == "cs.CL"  # Primary category

    # Access and rights
    assert normalized["open_access"] is True
    assert normalized["license"] == "http://creativecommons.org/licenses/by/4.0/"

    # API-specific fields
    assert normalized["primary_category"] == "cs.CL"
    assert normalized["comment"] == "45 pages, 12 figures, accepted at ACL 2024"
    assert normalized["updated_date"] == "2024-02-20T12:30:00Z"

    # PDF URL extraction
    assert normalized["pdf_url"] == "http://arxiv.org/pdf/2499.12345v2"

    # All categories should be extracted
    assert normalized["categories"] == ["cs.CL", "cs.AI", "cs.LG"]


def test_normalize_record_legacy_format(arxiv_sample_record_legacy):
    """Verifies that the normalization of legacy arXiv records (pre-2007 ID format) produces expected results."""
    normalized = arxiv_field_map.normalize_record(arxiv_sample_record_legacy)

    # Core identifiers - legacy format
    assert normalized["record_id"] == "hep-th/9711200v3"
    assert normalized["doi"] == "10.1023/A:1026654312961"

    assert "Maldacena" in str(normalized["authors"])
    assert "Large N Limit" in normalized["title"]

    assert normalized["year"] == 1997
    assert normalized["journal"] == "Adv.Theor.Math.Phys. 2 (1998) 231-252"

    assert normalized["subjects"] == "hep-th"

    assert normalized["open_access"] is True

    assert normalized["pdf_url"] == "http://arxiv.org/pdf/hep-th/9711200v3"

    # Single category (not list)
    assert normalized["categories"] == "hep-th"


def test_normalize_record_minimal():
    """Verifies that the normalization of minimal arXiv records correctly extracts and processes available fields."""
    minimal_record = {
        "id": "http://arxiv.org/abs/0000.00001",
        "title": "Minimal arXiv Record",
        "summary": "Abstract text.",
        "published": "2020-01-01",
    }
    normalized = arxiv_field_map.normalize_record(minimal_record)

    assert normalized["provider_name"] == "arxiv"
    assert normalized["record_id"] == "0000.00001"
    assert normalized["title"] == "Minimal arXiv Record"
    assert normalized["abstract"] == "Abstract text."
    assert normalized["year"] == 2020
    assert normalized["open_access"] is True
    assert normalized["doi"] is None
    assert normalized["authors"] is None


def test_normalize_record_batch(
    arxiv_sample_record_modern,
    arxiv_sample_record_legacy,
):
    """Verifies that batch normalization produces correct, normalized fields for both modern and legacy records."""
    records = [
        arxiv_sample_record_modern,
        arxiv_sample_record_legacy,
    ]

    normalized_list = arxiv_field_map.normalize_records(records)

    assert len(normalized_list) == 2

    # All arXiv records are open access
    assert all(n["open_access"] is True for n in normalized_list)

    # Verify ID formats
    assert normalized_list[0]["record_id"] == "2499.12345v2"  # Modern
    assert normalized_list[1]["record_id"] == "hep-th/9711200v3"  # Legacy
