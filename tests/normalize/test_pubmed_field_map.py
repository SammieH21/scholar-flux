"""Tests for PubMed field map normalization and post-processing.

This test suite covers:
1. Article ID extraction (DOI, PMCID, PII)
2. Author name formatting
3. Date extraction and formatting
4. URL reconstruction
5. Open access detection
6. Full normalization integration

"""

import pytest
from scholar_flux.api.normalization.pubmed_field_map import field_map as pubmed_field_map, PubMedFieldMap
from datetime import datetime, date


# ==================== Fixtures ====================


@pytest.fixture
def normalized_pubmed_record():
    """Normalized PubMed record (post parent-class processing) for testing extraction methods."""
    return {
        "record_id": "41418093",
        "title": "Sample PubMed Article",
        "abstract": "This is a sample abstract",
        "authors": [
            {"LastName": "Smith", "ForeName": "John"},
            {"LastName": "Johnson", "ForeName": "Jane"},
        ],
        "journal": "Journal of Sample Research",
        "year": "2024",
        "date_published": {"Year": "2024", "Month": "Dec", "Day": "18"},
        "date_created": {"Year": "2024", "Month": "12", "Day": "20"},
        "article_date": {"Year": "2024", "Month": "11", "Day": "15"},
        "pmid": "41418093",
        "article_id_list": {
            "ArticleId": [
                {"@IdType": "pubmed", "#text": "41418093"},
                {"@IdType": "doi", "#text": "10.1234/example"},
                {"@IdType": "pmc", "#text": "PMC1234567"},
                {"@IdType": "pii", "#text": "S1234-5678(24)00123-4"},
            ]
        },
        "elocation_id": [{"@EIdType": "doi", "#text": "10.1234/fallback"}],
    }


@pytest.fixture
def pubmed_sample_record():
    """Sample PubMed API record with complete structure for full normalization testing."""
    return {
        "MedlineCitation": {
            "PMID": {"#text": "41418093"},
            "Article": {
                "ArticleTitle": {"#text": "Sample PubMed Article"},
                "Abstract": {"AbstractText": {"#text": "This is a sample abstract"}},
                "AuthorList": {
                    "Author": [
                        {"LastName": "Smith", "ForeName": "John"},
                        {"LastName": "Johnson", "ForeName": "Jane"},
                    ]
                },
                "Journal": {
                    "Title": "Journal of Sample Research",
                    "JournalIssue": {"PubDate": {"Year": "2024", "Month": "Dec", "Day": "18"}},
                },
                "ELocationID": [{"@EIdType": "doi", "#text": "10.1234/elocation"}],
            },
            "DateCompleted": {"Year": "2024", "Month": "12", "Day": "20"},
        },
        "PubmedData": {
            "ArticleIdList": {
                "ArticleId": [
                    {"@IdType": "pubmed", "#text": "41418093"},
                    {"@IdType": "doi", "#text": "10.1234/example"},
                    {"@IdType": "pmc", "#text": "PMC1234567"},
                    {"@IdType": "pii", "#text": "S1234-5678(24)00123-4"},
                ]
            }
        },
    }


# ==================== Tests for _post_process ====================


def test_post_process_integration(normalized_pubmed_record):
    """Test _post_process method to verify all fields are correctly extracted and processed."""
    # Create an instance of PubMedFieldMap
    pubmed_map = PubMedFieldMap()

    # Apply _post_process to the normalized record
    processed_record = pubmed_map._post_process(normalized_pubmed_record)

    # Verify DOI extraction
    assert processed_record["doi"] == "10.1234/example"

    # Verify PMCID extraction with PMC prefix removed
    assert processed_record["pmcid"] == "1234567"

    # Verify PII extraction
    assert processed_record["pii"] == "S1234-5678(24)00123-4"

    # Verify authors extraction
    assert processed_record["authors"] == ["John Smith", "Jane Johnson"]

    # Verify date_published extraction
    assert processed_record["date_published"] == "2024-12-18"

    # Verify date_created extraction
    assert processed_record["date_created"] == "2024-12-20"

    # Verify open_access detection
    assert processed_record["open_access"] is True

    # Verify URL reconstruction
    assert processed_record["url"] == "https://pubmed.ncbi.nlm.nih.gov/41418093/"

    # Verify abstract extraction
    assert processed_record["abstract"] == "This is a sample abstract"


def test_post_process_edge_cases():
    """Test _post_process method with edge cases such as missing fields or invalid data."""
    # Create an instance of PubMedFieldMap
    pubmed_map = PubMedFieldMap()

    # Test with missing fields
    record_missing_fields = {
        "article_id_list": {"ArticleId": [{"@IdType": "pubmed", "#text": "12345"}]},
        "authors": [],
    }
    processed_record = pubmed_map._post_process(record_missing_fields)

    # Verify that otherwise available fields return None when not found
    assert processed_record["doi"] is None

    assert processed_record["pmcid"] is None

    assert processed_record["pii"] is None

    assert processed_record["authors"] is None

    assert processed_record["date_published"] is None

    assert processed_record["date_created"] is None

    # Verify open_access detection returns None when ArticleIdList is missing
    record_no_article_id_list = {"title": "Article without IDs"}
    processed_record_no_ids = pubmed_map._post_process(record_no_article_id_list)
    assert processed_record_no_ids["open_access"] is None

    # URL reconstruction should return None when PMID is missing
    record_no_pmid = {"article_id_list": {"ArticleId": [{"@IdType": "doi", "#text": "10.1234/test"}]}}
    processed_record_no_pmid = pubmed_map._post_process(record_no_pmid)
    assert processed_record_no_pmid["url"] is None

    # Abstract extraction should also return None when not a string or list of strings
    record_invalid_abstract = {"abstract": 123}
    processed_record_invalid_abstract = pubmed_map._post_process(record_invalid_abstract)
    assert processed_record_invalid_abstract["abstract"] is None


# ==================== Tests for DOI Extraction ====================


def test_basic_doi_extraction(normalized_pubmed_record):
    """Verifies that basic PubMed DOI retrieves valid DOIs from the ArticleIdList (primary source)."""
    doi = PubMedFieldMap.extract_doi(normalized_pubmed_record)
    assert doi == "10.1234/example"  # Not "10.1234/fallback"


def test_extract_doi_fallback_elocation_extraction():
    """Verifies that PubMed DOI extraction falls back to ELocationID when a `DOI` ID tag is missing."""
    record = {
        "article_id_list": {"ArticleId": [{"@IdType": "pubmed", "#text": "123"}]},
        "elocation_id": [{"@EIdType": "doi", "#text": "10.1234/elocation"}],
    }
    doi = PubMedFieldMap.extract_doi(record)
    assert doi == "10.1234/elocation"


# ==================== Tests for Date Extraction ====================


@pytest.mark.parametrize(
    "record,expected",
    [
        ({"date_published": {"Year": "2024"}}, "2024"),
        ({"date_published": date(2024, 12, 12)}, "2024-12-12"),
        ({"date_published": datetime(2024, 12, 12, 0, 0, 0)}, "2024-12-12"),
        ({"date_published": None}, None),
        ({}, None),
    ],
)
def test_extract_date_published(record, expected):
    """Verifies that article publication date extraction works as intended with several inputs."""
    date = PubMedFieldMap.extract_iso_date(record, "date_published")
    assert date == expected


def test_extract_date_created_from_date_created(normalized_pubmed_record):
    """Test date created extraction from DateCompleted."""
    date = PubMedFieldMap.extract_date_created(normalized_pubmed_record)
    assert date == "2024-12-20"


@pytest.mark.parametrize(
    "record,expected",
    [
        ({"article_date": {"Year": "2024", "Month": "11", "Day": "15"}}, "2024-11-15"),
        ({"date_created": {"Year": "2024", "Month": "12", "Day": "20"}}, "2024-12-20"),
        ({}, None),
    ],
)
def test_extract_date_created(record, expected):
    """Verifies that article creation date extraction works as intended with several inputs."""
    date = PubMedFieldMap.extract_date_created(record)
    assert date == expected


# ==================== Tests for URL Reconstruction ====================


def test_reconstruct_pubmed_url_valid_pmid():
    """Test URL reconstruction with valid PMID."""
    url = PubMedFieldMap.reconstruct_pubmed_url({"pmid": "41418093"})
    assert url == "https://pubmed.ncbi.nlm.nih.gov/41418093/"


def test_reconstruct_pubmed_url_with_whitespace():
    """Test URL reconstruction strips whitespace from PMID."""
    url = PubMedFieldMap.reconstruct_pubmed_url({"pmid": "  41418093  "})
    assert url == "https://pubmed.ncbi.nlm.nih.gov/41418093/"


def test_reconstruct_pubmed_url_none():
    """Test URL reconstruction returns None for None input."""
    url = PubMedFieldMap.reconstruct_pubmed_url({"pmid": None})
    assert url is None


def test_reconstruct_pubmed_url_empty():
    """Test URL reconstruction returns None for empty string."""
    url = PubMedFieldMap.reconstruct_pubmed_url({"pmid": ""})
    assert url is None


def test_reconstruct_pubmed_url_invalid_type():
    """Test URL reconstruction returns None for non-string input."""
    url = PubMedFieldMap.reconstruct_pubmed_url({"pmid": 41418093})
    assert url is None


# ==================== Tests for Abstract Extraction ====================


def test_basic_extract_abstract():
    """Tests that abstract information is returned as is when the type is a string."""
    record = {"abstract": "Research exploring computational approaches..."}
    abstract_data = PubMedFieldMap.extract_abstract(record)
    assert abstract_data == record["abstract"]


@pytest.mark.parametrize("abstract_input", (23, {45}, {"6": 67}, None))
def test_extract_abstract_data_returns_none_when_incorrect_type(abstract_input):
    """Verifies that attempting to extract a non-list or non-string abstract record field will return None."""
    record = {"abstract": abstract_input}
    abstract_data = PubMedFieldMap.extract_abstract(record)
    assert abstract_data is None


def test_extract_abstract_with_list_of_strings():
    """Tests that abstracts that come in the form of lists of strings can be extracted as a single string."""
    mock_abstract = [
        "Title: A mock abstract",
        "Summary: An abstract summary",
        "Keywords: Testing, programming, computational methods",
    ]
    record = {"abstract": mock_abstract}
    abstract_data = PubMedFieldMap.extract_abstract(record)
    assert abstract_data == " ".join(mock_abstract)


# ==================== Full Normalization Integration ====================


def test_pubmed_record_normalization(pubmed_sample_record):
    """Tests the integration of the PubMed record post-processing step as the last step of the normalization process."""
    normalized = pubmed_field_map.normalize_record(pubmed_sample_record)

    # Verify core fields
    assert normalized["record_id"] == "41418093"
    assert normalized["title"] == "Sample PubMed Article"
    assert normalized["abstract"] == "This is a sample abstract"
    assert normalized["journal"] == "Journal of Sample Research"
    assert normalized["year"] == 2024

    # Verify extracted identifiers
    assert normalized["doi"] == "10.1234/example"
    assert normalized["pmcid"] == "1234567"
    assert normalized["pii"] == "S1234-5678(24)00123-4"
    assert normalized["url"] == "https://pubmed.ncbi.nlm.nih.gov/41418093/"

    # Verify extracted authors
    assert normalized["authors"] == ["John Smith", "Jane Johnson"]

    # Verify dates
    assert normalized["date_published"] == "2024-12-18"
    assert normalized["date_created"] == "2024-12-20"

    # Verify open access
    assert normalized["open_access"] is True
