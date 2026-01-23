"""Tests for record resolution functionality in ProcessedResponse.

This test suite covers:
1. Record ID index building from extracted records
2. Extracted record resolution from processed record indices
3. Annotation stripping for clean data export
4. Normalization record preparation and merging
5. Edge cases for malformed data and type handling
6. SearchResult delegation to ProcessedResponse

"""

import pytest
from unittest.mock import MagicMock

from scholar_flux.api.models import ProcessedResponse, ReconstructedResponse, SearchResult
from scholar_flux.data.data_extractor import DataExtractor


# ==================== Fixtures ====================


@pytest.fixture
def sample_extracted_records() -> list[dict]:
    """Fixture containing extracted records with nested structure and annotation fields."""
    return [
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 0,
            DataExtractor.RECORD_ID_KEY: "abc123def456_0",
            "title": "Machine Learning in Healthcare",
            "author": {"name": "Smith", "affiliation": {"institution": "MIT", "department": "CSAIL"}},
            "metadata": {"doi": "10.1234/ml.2024.001", "year": 2024},
        },
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 1,
            DataExtractor.RECORD_ID_KEY: "def456abc789_1",
            "title": "Deep Learning for NLP",
            "author": {"name": "Jones", "affiliation": {"institution": "Stanford", "department": "NLP Lab"}},
            "metadata": {"doi": "10.1234/dl.2024.002", "year": 2024},
        },
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 2,
            DataExtractor.RECORD_ID_KEY: "ghi789jkl012_2",
            "title": "Reinforcement Learning Survey",
            "author": {"name": "Williams", "affiliation": {"institution": "Berkeley", "department": "BAIR"}},
            "metadata": {"doi": "10.1234/rl.2024.003", "year": 2023},
        },
    ]


@pytest.fixture
def sample_nonmatching_extracted_records(sample_extracted_records) -> list[dict]:
    """Fixture containing extracted records with annotation fields that don't match processed records."""
    return [
        record | {DataExtractor.RECORD_ID_KEY: record[DataExtractor.RECORD_ID_KEY] * 3}
        for record in sample_extracted_records
    ]


@pytest.fixture
def sample_extracted_records_with_int_ids(sample_extracted_records) -> list[dict]:
    """Fixture containing extracted records with integer IDs instead of strings."""
    return [record | {DataExtractor.RECORD_ID_KEY: id} for id, record in enumerate(sample_extracted_records)]


@pytest.fixture
def sample_processed_records() -> list[dict]:
    """Fixture containing processed (flattened) records with annotation fields preserved."""
    return [
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 0,
            DataExtractor.RECORD_ID_KEY: "abc123def456_0",
            "title": "Machine Learning in Healthcare",
            "author.name": "Smith",
            "author.affiliation.institution": "MIT",
            "metadata.doi": "10.1234/ml.2024.001",
        },
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 1,
            DataExtractor.RECORD_ID_KEY: "def456abc789_1",
            "title": "Deep Learning for NLP",
            "author.name": "Jones",
            "author.affiliation.institution": "Stanford",
            "metadata.doi": "10.1234/dl.2024.002",
        },
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 2,
            DataExtractor.RECORD_ID_KEY: "ghi789jkl012_2",
            "title": "Reinforcement Learning Survey",
            "author.name": "Williams",
            "author.affiliation.institution": "Berkeley",
            "metadata.doi": "10.1234/rl.2024.003",
        },
    ]


@pytest.fixture
def nested_processed_records() -> list[dict]:
    """Fixture containing processed records that retain their nested structure after processing.

    Records are similarly nested when using the default `PassthroughDataProcessor` during response record processing.

    """
    return [
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 0,
            DataExtractor.RECORD_ID_KEY: "abc123_0",
            "title": "Test Article",
            "author": {"name": "Smith", "affiliation": "MIT"},
            "metadata": {"doi": "10.1234/test"},
        },
    ]


@pytest.fixture
def flattened_processed_records() -> list[dict]:
    """Fixture containing processed records with a flattened record structure.

    Flattened records like these generally appear only when a `RecursiveDataProcessor` or `PathDataProcessor` is used to
    process extracted records.

    """
    return [
        {
            DataExtractor.EXTRACTION_INDEX_KEY: 0,
            DataExtractor.RECORD_ID_KEY: "abc123_0",
            "title": "Test Article",
            "author.name": "Smith",
            "author.affiliation": "MIT",
            "metadata.doi": "10.1234/test",
        },
    ]


@pytest.fixture
def response_with_annotations(sample_extracted_records, sample_processed_records) -> ProcessedResponse:
    """Fixture of a ProcessedResponse containing both extracted and processed records."""
    return ProcessedResponse(
        extracted_records=sample_extracted_records,
        processed_records=sample_processed_records,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


@pytest.fixture
def response_with_nonmatching_annotations(
    sample_nonmatching_extracted_records, sample_processed_records
) -> ProcessedResponse:
    """Fixture containing a ProcessedResponse with non-matching record annotation fields."""
    return ProcessedResponse(
        extracted_records=sample_nonmatching_extracted_records,
        processed_records=sample_processed_records,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


@pytest.fixture
def response_with_nonstring_id_annotations(
    sample_extracted_records_with_int_ids, sample_processed_records
) -> ProcessedResponse:
    """Fixture containing a ProcessedResponse with non-string record ID annotations."""
    return ProcessedResponse(
        extracted_records=sample_extracted_records_with_int_ids,
        processed_records=sample_processed_records,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


@pytest.fixture
def response_without_annotations() -> ProcessedResponse:
    """Fixture containing a ProcessedResponse without annotation fields."""
    extracted = [{"title": "Test", "nested": {"value": 1}}]
    processed = [{"title": "Test", "nested.value": 1}]
    return ProcessedResponse(
        extracted_records=extracted,
        processed_records=processed,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


# ==================== Record ID Index Building ====================


def test_build_record_id_index_maps_ids_to_records(response_with_annotations):
    """Verifies that `build_record_id_index` correctly maps record IDs to extracted records."""
    index = response_with_annotations.build_record_id_index()

    assert len(index) == 3
    assert "abc123def456_0" in index
    assert "def456abc789_1" in index
    assert "ghi789jkl012_2" in index
    assert index["abc123def456_0"]["title"] == "Machine Learning in Healthcare"
    assert index["def456abc789_1"]["author"]["name"] == "Jones"


def test_build_record_id_index_returns_empty_dict_when_no_records():
    """Verifies that `build_record_id_index` returns an empty dict when extracted_records is None or empty."""
    response = ProcessedResponse(extracted_records=None)
    assert response.build_record_id_index() == {}

    response = ProcessedResponse(extracted_records=[])
    assert response.build_record_id_index() == {}


def test_build_record_id_index_skips_records_without_valid_ids():
    """Verifies that records without a valid string _record_id are excluded from the index."""
    extracted: list[dict] = [
        {DataExtractor.RECORD_ID_KEY: "valid_id", "title": "Has ID"},
        {"title": "No ID"},
        {DataExtractor.RECORD_ID_KEY: None, "title": "None ID"},
        {DataExtractor.RECORD_ID_KEY: 123, "title": "Non-string ID"},
    ]
    response = ProcessedResponse(extracted_records=extracted)
    index = response.build_record_id_index()

    assert len(index) == 1
    assert "valid_id" in index


def test_build_record_id_index_skips_empty_records():
    """Verifies that empty records in the extracted list are handled gracefully."""
    extracted = [
        {DataExtractor.RECORD_ID_KEY: "valid_id", "title": "Valid"},
        {},
    ]
    response = ProcessedResponse(extracted_records=extracted)  # type: ignore
    index = response.build_record_id_index()

    assert len(index) == 1


def test_build_record_id_index_last_duplicate_wins():
    """Verifies that when multiple records share the same _record_id, the last one is retained."""
    extracted = [
        {DataExtractor.RECORD_ID_KEY: "duplicate_id", "title": "First"},
        {DataExtractor.RECORD_ID_KEY: "duplicate_id", "title": "Second"},
    ]
    response = ProcessedResponse(extracted_records=extracted)
    index = response.build_record_id_index()

    assert len(index) == 1
    assert index["duplicate_id"]["title"] == "Second"


# ==================== Extracted Record Resolution ====================


def test_resolve_extracted_record_by_index(response_with_annotations):
    """Verifies that `resolve_extracted_record` returns the correct record by index."""
    original = response_with_annotations.resolve_extracted_record(0)

    assert original is not None
    assert original["title"] == "Machine Learning in Healthcare"
    assert original["author"]["name"] == "Smith"
    assert original["author"]["affiliation"]["institution"] == "MIT"


def test_resolve_extracted_record_all_indices(response_with_annotations):
    """Verifies that all records can be resolved by their processed index."""
    for i in range(3):
        original = response_with_annotations.resolve_extracted_record(i)
        assert original is not None
        assert original[DataExtractor.EXTRACTION_INDEX_KEY] == i


def test_resolve_extracted_record_returns_none_for_invalid_index(response_with_annotations):
    """Verifies that None is returned for out-of-bounds indices."""
    assert response_with_annotations.resolve_extracted_record(-1) is None
    assert response_with_annotations.resolve_extracted_record(100) is None


def test_resolve_extracted_record_returns_none_when_no_records():
    """Verifies that None is returned when processed_records or extracted_records are missing."""
    response = ProcessedResponse(processed_records=None, extracted_records=None)
    assert response.resolve_extracted_record(0) is None

    response = ProcessedResponse(processed_records=[{"title": "Test"}], extracted_records=None)
    assert response.resolve_extracted_record(0) is None


def test_resolve_extracted_record_validates_id(response_with_annotations):
    """Verifies that ID validation catches mismatches (default)."""
    response_with_annotations.extracted_records[0][DataExtractor.RECORD_ID_KEY] = "corrupted_id"
    original = response_with_annotations.resolve_extracted_record(0)
    assert original is None


def test_resolve_extracted_record(sample_extracted_records, sample_processed_records):
    """Verifies that record extractions falls back to a linear search when index-based lookup fails."""
    reordered_processed = [
        sample_processed_records[2],
        sample_processed_records[0],
        sample_processed_records[1],
    ]
    response = ProcessedResponse(
        extracted_records=sample_extracted_records,
        processed_records=reordered_processed,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com"),
    )

    original = response.resolve_extracted_record(0)
    assert original is not None
    assert original["title"] == "Reinforcement Learning Survey"


def test_resolve_extracted_record_returns_none_without_annotations(response_without_annotations):
    """Verifies that None is returned when records lack metadata annotations."""
    original = response_without_annotations.resolve_extracted_record(0)
    assert original is None


def test_resolve_by_record_id_finds_correct_record(response_with_annotations):
    """Verifies that `_resolve_by_record_id` finds the correct record by ID."""
    original = response_with_annotations._resolve_by_record_id("def456abc789_1")

    assert original is not None
    assert original["title"] == "Deep Learning for NLP"


def test_resolve_by_record_id_returns_none_for_unknown_id(response_with_annotations):
    """Verifies that `_resolve_by_record_id` returns None for non-existent IDs."""
    assert response_with_annotations._resolve_by_record_id("nonexistent_id") is None


def test_resolve_by_record_id_returns_none_when_no_extracted_records():
    """Verifies that `_resolve_by_record_id` returns None when extracted_records is empty."""
    response = ProcessedResponse(extracted_records=None)
    assert response._resolve_by_record_id("any_id") is None


# ==================== Resolution Fallback Edge Cases ====================


def test_fallback_when_extraction_index_out_of_bounds():
    """Verifies that fallback to ID search occurs when _extraction_index exceeds list length."""
    extracted = [{DataExtractor.RECORD_ID_KEY: "id_0", "title": "Only One"}]
    processed = [
        {
            DataExtractor.RECORD_ID_KEY: "id_0",
            DataExtractor.EXTRACTION_INDEX_KEY: 999,
            "title": "Only One",
        },
    ]
    response = ProcessedResponse(extracted_records=extracted, processed_records=processed)

    original = response.resolve_extracted_record(0)
    assert original is not None
    assert original["title"] == "Only One"


def test_fallback_when_extraction_index_negative():
    """Verifies that negative _extraction_index values trigger fallback to ID search."""
    extracted = [{DataExtractor.RECORD_ID_KEY: "id_0", "title": "Test"}]
    processed = [
        {
            DataExtractor.RECORD_ID_KEY: "id_0",
            DataExtractor.EXTRACTION_INDEX_KEY: -1,
            "title": "Test",
        },
    ]
    response = ProcessedResponse(extracted_records=extracted, processed_records=processed)

    original = response.resolve_extracted_record(0)
    assert original is not None


def test_resolution_returns_none_when_all_methods_fail():
    """Verifies that None is returned when both index and ID resolution fail."""
    extracted = [{DataExtractor.RECORD_ID_KEY: "different_id", "title": "Test"}]
    processed = [
        {
            DataExtractor.RECORD_ID_KEY: "nonexistent_id",
            DataExtractor.EXTRACTION_INDEX_KEY: 999,
            "title": "Orphan",
        },
    ]
    response = ProcessedResponse(extracted_records=extracted, processed_records=processed)

    original = response.resolve_extracted_record(0)
    assert original is None


# ==================== Annotation Stripping ====================


def test_strip_annotations_removes_internal_fields(response_with_annotations):
    """Verifies that `strip_annotations` removes annotation fields from records."""
    clean = response_with_annotations.strip_annotations()

    assert len(clean) == 3
    for record in clean:
        assert DataExtractor.EXTRACTION_INDEX_KEY not in record
        assert DataExtractor.RECORD_ID_KEY not in record


def test_strip_annotations_preserves_regular_fields(response_with_annotations):
    """Verifies that regular fields are preserved after stripping annotations."""
    clean = response_with_annotations.strip_annotations()

    assert clean[0]["title"] == "Machine Learning in Healthcare"
    assert clean[0]["author.name"] == "Smith"
    assert clean[1]["metadata.doi"] == "10.1234/dl.2024.002"


def test_strip_annotations_returns_new_list(response_with_annotations):
    """Verifies that `strip_annotations` returns a new list without mutating the original."""
    original_records = response_with_annotations.processed_records
    clean = response_with_annotations.strip_annotations()

    assert DataExtractor.EXTRACTION_INDEX_KEY in original_records[0]
    assert DataExtractor.RECORD_ID_KEY in original_records[0]
    assert DataExtractor.EXTRACTION_INDEX_KEY not in clean[0]


def test_strip_annotations_accepts_custom_records(response_with_annotations):
    """Verifies that custom records can be passed to `strip_annotations`."""
    custom_records = [{"_custom_field": "value", "_record_id": "id", "title": "Test"}]
    clean = response_with_annotations.strip_annotations(records=custom_records)

    assert len(clean) == 1
    assert "_custom_field" not in clean[0]
    assert "_record_id" not in clean[0]
    assert clean[0]["title"] == "Test"


def test_strip_annotations_returns_empty_list_when_no_records():
    """Verifies that an empty list is returned when no records are available."""
    response = ProcessedResponse(processed_records=None)
    assert response.strip_annotations() == []

    response = ProcessedResponse(processed_records=[])
    assert response.strip_annotations() == []


def test_strip_annotations_preserves_integer_keys():
    """Verifies that integer keys (common in XML parsing) are preserved during stripping."""
    records: list[dict] = [{0: "xml_value", "_annotation": "strip", "title": "Keep"}]
    response = ProcessedResponse(processed_records=records)
    clean = response.strip_annotations()

    assert 0 in clean[0]
    assert "_annotation" not in clean[0]
    assert clean[0]["title"] == "Keep"


# ==================== Normalization Record Preparation ====================


def test_prepare_normalization_records_merges_when_annotations_present(response_with_annotations):
    """Verifies that extracted and processed records are merged when annotations exist."""
    merged = response_with_annotations._prepare_normalization_records()

    assert merged is not None
    assert len(merged) == 3

    first = merged[0]
    assert first["author"]["name"] == "Smith"
    assert first["author.name"] == "Smith"


def test_prepare_normalization_records_skips_merge_when_disabled(response_with_annotations):
    """Verifies that `processed_records` is returned when using resolve_records=False."""
    processed_records = response_with_annotations._prepare_normalization_records(resolve_records=False)
    assert processed_records is response_with_annotations.processed_records


def test_prepare_normalization_records_skips_merge_with_nonstring_ids(response_with_nonstring_id_annotations):
    """Verifies that `processed_records` is returned when ID annotations are non-string types."""
    processed_records = response_with_nonstring_id_annotations._prepare_normalization_records()
    assert processed_records is response_with_nonstring_id_annotations.processed_records


def test_prepare_normalization_records_skips_merge_with_nonmatching_ids(response_with_nonmatching_annotations):
    """Verifies that `processed_records` is returned when annotations don't match."""
    processed_records = response_with_nonmatching_annotations._prepare_normalization_records()
    assert processed_records == response_with_nonmatching_annotations.processed_records


def test_prepare_normalization_records_returns_processed_when_no_annotations(response_without_annotations):
    """Verifies that `processed_records` is returned unchanged when no annotations exist."""
    result = response_without_annotations._prepare_normalization_records()
    assert result is response_without_annotations.processed_records


def test_prepare_normalization_records_returns_processed_when_no_extracted(sample_processed_records):
    """Verifies that `processed_records` is returned when extracted_records is missing."""
    response = ProcessedResponse(extracted_records=None, processed_records=sample_processed_records)
    result = response._prepare_normalization_records()
    assert result is response.processed_records


def test_prepare_normalization_records_returns_extracted_when_no_processed(sample_extracted_records):
    """Verifies that `extracted_records` is returned when processed_records is missing."""
    response = ProcessedResponse(extracted_records=sample_extracted_records, processed_records=None)
    result = response._prepare_normalization_records()
    assert result is response.extracted_records


def test_prepare_normalization_records_returns_none_when_empty():
    """Verifies that None is returned when both record lists are missing."""
    response = ProcessedResponse(extracted_records=None, processed_records=None)
    result = response._prepare_normalization_records()
    assert result is None


def test_prepare_normalization_records_processed_fields_override(response_with_annotations):
    """Verifies that processed fields take precedence in merged records."""
    response_with_annotations.processed_records[0]["title"] = "Modified Title"
    merged = response_with_annotations._prepare_normalization_records()

    assert merged[0]["title"] == "Modified Title"


def test_prepare_normalization_records_skips_merge_when_nested(nested_processed_records):
    """Verifies that no merge is performed when processed records retain nested structure."""
    response = ProcessedResponse(
        extracted_records=nested_processed_records,
        processed_records=nested_processed_records,
    )
    result = response._prepare_normalization_records()
    assert result is not None


def test_prepare_normalization_records_performs_merge_when_flattened(
    nested_processed_records, flattened_processed_records
):
    """Verifies that merge is performed when processed records are flattened."""
    response = ProcessedResponse(
        extracted_records=nested_processed_records,
        processed_records=flattened_processed_records,
    )
    result = response._prepare_normalization_records()

    assert result is not None
    assert "author" in result[0]
    assert "author.name" in result[0]


# ==================== Record Pair Merging ====================


def test_merge_record_pair_combines_extracted_and_processed(response_with_annotations):
    """Verifies that `_merge_record_pair` correctly merges extracted and processed records."""
    id_index = response_with_annotations.build_record_id_index()
    processed = response_with_annotations.processed_records[0]

    merged = response_with_annotations._merge_record_pair(processed, id_index)

    assert "author" in merged
    assert merged["author"]["affiliation"]["department"] == "CSAIL"
    assert merged["author.name"] == "Smith"


def test_merge_record_pair_returns_processed_when_no_match(response_with_annotations):
    """Verifies that processed record is returned when no matching extracted record exists."""
    id_index = response_with_annotations.build_record_id_index()
    unmatched = {DataExtractor.RECORD_ID_KEY: "unknown_id", "title": "Orphan"}

    result = response_with_annotations._merge_record_pair(unmatched, id_index)
    assert result is unmatched


def test_merge_record_pair_returns_processed_when_no_record_id(response_with_annotations):
    """Verifies that processed record is returned when _record_id is missing or invalid."""
    id_index = response_with_annotations.build_record_id_index()

    no_id = {"title": "No ID"}
    assert response_with_annotations._merge_record_pair(no_id, id_index) is no_id

    bad_id = {DataExtractor.RECORD_ID_KEY: 12345, "title": "Bad ID"}
    assert response_with_annotations._merge_record_pair(bad_id, id_index) is bad_id


# ==================== Malformed Data Handling ====================


def test_handles_empty_processed_record():
    """Verifies that empty records in processed_records don't cause errors."""
    extracted = [{DataExtractor.RECORD_ID_KEY: "id_0", "title": "Test"}]
    processed: list[dict] = [{}]

    response = ProcessedResponse(extracted_records=extracted, processed_records=processed)
    result = response._prepare_normalization_records()
    assert result is response.processed_records


def test_handles_mismatched_record_counts():
    """Verifies that mismatched extracted and processed record counts are handled gracefully."""
    extracted = [
        {DataExtractor.RECORD_ID_KEY: "id_0", DataExtractor.EXTRACTION_INDEX_KEY: 0, "title": "One"},
        {DataExtractor.RECORD_ID_KEY: "id_1", DataExtractor.EXTRACTION_INDEX_KEY: 1, "title": "Two"},
    ]
    processed = [
        {DataExtractor.RECORD_ID_KEY: "id_0", DataExtractor.EXTRACTION_INDEX_KEY: 0, "title": "One"},
    ]

    response = ProcessedResponse(extracted_records=extracted, processed_records=processed)
    result = response._prepare_normalization_records()

    assert result is not None
    assert len(result) == 1


def test_handles_none_values_in_records():
    """Verifies that None values in record fields are handled gracefully."""
    extracted = [
        {
            DataExtractor.RECORD_ID_KEY: "id_0",
            DataExtractor.EXTRACTION_INDEX_KEY: 0,
            "title": None,
            "author": None,
        },
    ]
    processed = [
        {
            DataExtractor.RECORD_ID_KEY: "id_0",
            DataExtractor.EXTRACTION_INDEX_KEY: 0,
            "title": None,
        },
    ]

    response = ProcessedResponse(extracted_records=extracted, processed_records=processed)
    result = response._prepare_normalization_records()

    assert result is not None
    assert result[0]["title"] is None


def test_preserves_various_value_types():
    """Verifies that various value types are preserved through resolution."""
    extracted = [
        {
            DataExtractor.RECORD_ID_KEY: "id_0",
            DataExtractor.EXTRACTION_INDEX_KEY: 0,
            "count": 42,
            "ratio": 3.14,
            "active": True,
            "tags": ["ml", "nlp"],
            "nested": {"deep": {"value": 1}},
        },
    ]
    response = ProcessedResponse(extracted_records=extracted)
    index = response.build_record_id_index()

    record = index["id_0"]
    assert record["count"] == 42
    assert record["ratio"] == 3.14
    assert record["active"] is True
    assert record["tags"] == ["ml", "nlp"]
    assert record["nested"]["deep"]["value"] == 1


# ==================== Integration Tests ====================


def test_full_resolution_workflow(sample_extracted_records, sample_processed_records):
    """Verifies the complete workflow: extract, process, resolve, and access nested data."""
    response = ProcessedResponse(
        extracted_records=sample_extracted_records,
        processed_records=sample_processed_records,
    )

    assert response.extracted_records and response.processed_records
    for i, processed in enumerate(response.processed_records):
        assert isinstance(processed, dict) and "author.name" in processed

        original = response.resolve_extracted_record(i)
        assert original is not None

        department = original["author"]["affiliation"]["department"]
        assert department in ("CSAIL", "NLP Lab", "BAIR")


def test_batch_resolution_via_index(response_with_annotations):
    """Verifies that batch resolution using a pre-built index works correctly."""
    id_index = response_with_annotations.build_record_id_index()

    resolved = []
    for processed in response_with_annotations.processed_records:
        record_id = processed.get(DataExtractor.RECORD_ID_KEY)
        if record_id:
            resolved.append(id_index.get(record_id))

    assert len(resolved) == 3
    assert all(r is not None for r in resolved)


def test_strip_for_dataframe_export(response_with_annotations):
    """Verifies that stripped annotations produce clean records suitable for DataFrame export."""
    clean_records = response_with_annotations.strip_annotations()

    for record in clean_records:
        assert not any(k.startswith("_") for k in record if isinstance(k, str))
        assert "title" in record
        assert "author.name" in record


def test_normalize_uses_merged_records(response_with_annotations):
    """Verifies that `normalize()` receives merged records when annotations are present."""
    mock_field_map = MagicMock()
    mock_field_map.normalize_records.return_value = [{"normalized": True}]

    response_with_annotations.normalize(field_map=mock_field_map)

    call_args = mock_field_map.normalize_records.call_args[0][0]
    assert "author" in call_args[0]
    assert "author.name" in call_args[0]


def test_search_result_resolve_extracted_record_delegates_to_response(
    sample_extracted_records, sample_processed_records
):
    """Verifies that `SearchResult.resolve_extracted_record` delegates extraction to the ProcessedResponse."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(
        response=mock_response,
        extracted_records=sample_extracted_records,
        processed_records=sample_processed_records,
    )
    search_result = SearchResult(response_result=response, query="test_query", provider_name="mock_provider", page=1)

    assert all(
        search_result.resolve_extracted_record(record["_extraction_index"])
        == response.resolve_extracted_record(record["_extraction_index"])
        for record in response.processed_records or []
    )


def test_search_result_build_record_id_index_delegates_to_response(sample_extracted_records, sample_processed_records):
    """Verifies that `SearchResult.build_record_id_index` delegates index creation to the ProcessedResponse."""
    mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
    response = ProcessedResponse(
        response=mock_response,
        extracted_records=sample_extracted_records,
        processed_records=sample_processed_records,
    )
    search_result = SearchResult(response_result=response, query="test_query", provider_name="mock_provider", page=1)

    response_id_index = response.build_record_id_index()
    assert response_id_index and response_id_index == search_result.build_record_id_index()
