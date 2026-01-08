# tests/normalize/test_response_record_resolution.py
"""Tests for record resolution functionality in ProcessedResponse.

This module tests the ability to resolve processed (flattened) records back to their
original extracted (nested) structure using annotation fields added during extraction.

The resolution system uses two annotation fields:
    - `_extraction_index`: Zero-based position in extracted_records
    - `_record_id`: Content-based hash for validation and fallback lookup

Resolution Strategy:
    1. O(1) index-based lookup via `_extraction_index`
    2. O(n) fallback search by `_record_id` if index lookup fails

"""
import pytest

from scholar_flux.api.models import ProcessedResponse, ReconstructedResponse
from scholar_flux.data.data_extractor import DataExtractor
from scholar_flux.api.models import SearchResult
from unittest.mock import MagicMock


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_extracted_records() -> list[dict]:
    """Extracted records with nested structure and annotation fields."""
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
    """Extracted records with nested structure and annotation fields when they don't resolve to processed records."""
    return [
        record | {DataExtractor.RECORD_ID_KEY: record[DataExtractor.RECORD_ID_KEY] * 3}
        for record in sample_extracted_records
    ]


@pytest.fixture
def sample_extracted_records_with_int_ids(sample_extracted_records) -> list[dict]:
    """Extracted records with nested structure and annotated IDs that don't have the expected string data type."""
    return [record | {DataExtractor.RECORD_ID_KEY: id} for id, record in enumerate(sample_extracted_records)]


@pytest.fixture
def sample_processed_records() -> list[dict]:
    """Processed (flattened) records with annotation fields preserved."""
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
def response_with_annotations(sample_extracted_records, sample_processed_records) -> ProcessedResponse:
    """ProcessedResponse with both extracted and processed records containing annotations."""
    return ProcessedResponse(
        extracted_records=sample_extracted_records,
        processed_records=sample_processed_records,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


@pytest.fixture
def response_with_nonmatching_annotations(
    sample_nonmatching_extracted_records, sample_processed_records
) -> ProcessedResponse:
    """ProcessedResponse with both extracted and processed records containing annotations."""
    return ProcessedResponse(
        extracted_records=sample_nonmatching_extracted_records,
        processed_records=sample_processed_records,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


@pytest.fixture
def response_with_nonstring_id_annotations(
    sample_extracted_records_with_int_ids, sample_processed_records
) -> ProcessedResponse:
    """ProcessedResponse with extracted_record annotated IDs that don't match the expected data type."""
    return ProcessedResponse(
        extracted_records=sample_extracted_records_with_int_ids,
        processed_records=sample_processed_records,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


@pytest.fixture
def response_without_annotations() -> ProcessedResponse:
    """ProcessedResponse without annotation fields (legacy/passthrough processing)."""
    extracted = [{"title": "Test", "nested": {"value": 1}}]
    processed = [{"title": "Test", "nested.value": 1}]
    return ProcessedResponse(
        extracted_records=extracted,
        processed_records=processed,
        response=ReconstructedResponse.build(status_code=200, url="https://api.example.com/search"),
    )


# =============================================================================
# build_record_id_index Tests
# =============================================================================


class TestBuildRecordIdIndex:
    """Tests for ProcessedResponse.build_record_id_index()."""

    def test_builds_index_from_extracted_records(self, response_with_annotations):
        """Verify index correctly maps record IDs to extracted records."""
        index = response_with_annotations.build_record_id_index()

        assert len(index) == 3
        assert "abc123def456_0" in index
        assert "def456abc789_1" in index
        assert "ghi789jkl012_2" in index

        # Verify records are the actual extracted records
        assert index["abc123def456_0"]["title"] == "Machine Learning in Healthcare"
        assert index["def456abc789_1"]["author"]["name"] == "Jones"

    def test_returns_empty_dict_when_no_extracted_records(self):
        """Verify empty dict returned when extracted_records is None or empty."""
        response = ProcessedResponse(extracted_records=None)
        assert response.build_record_id_index() == {}

        response = ProcessedResponse(extracted_records=[])
        assert response.build_record_id_index() == {}

    def test_skips_records_without_record_id(self):
        """Verify records without _record_id are excluded from index."""
        extracted: list[dict] = [
            {DataExtractor.RECORD_ID_KEY: "valid_id", "title": "Has ID"},
            {"title": "No ID"},  # Missing _record_id
            {DataExtractor.RECORD_ID_KEY: None, "title": "None ID"},  # None value
            {DataExtractor.RECORD_ID_KEY: 123, "title": "Non-string ID"},  # Non-string
        ]
        response = ProcessedResponse(extracted_records=extracted)
        index = response.build_record_id_index()

        assert len(index) == 1
        assert "valid_id" in index

    def test_skips_empty_records(self):
        """Verify empty/None records in list are handled gracefully."""
        extracted = [
            {DataExtractor.RECORD_ID_KEY: "valid_id", "title": "Valid"},
            {},  # Empty dict
        ]
        response = ProcessedResponse(extracted_records=extracted)  # type: ignore
        index = response.build_record_id_index()

        assert len(index) == 1


# =============================================================================
# resolve_extracted_record Tests
# =============================================================================


class TestResolveExtractedRecord:
    """Tests for ProcessedResponse.resolve_extracted_record()."""

    def test_resolves_by_index_when_valid(self, response_with_annotations):
        """Verify O(1) index-based resolution works correctly."""
        original = response_with_annotations.resolve_extracted_record(0)

        assert original is not None
        assert original["title"] == "Machine Learning in Healthcare"
        # Verify nested structure preserved
        assert original["author"]["name"] == "Smith"
        assert original["author"]["affiliation"]["institution"] == "MIT"

    def test_resolves_all_records_by_index(self, response_with_annotations):
        """Verify all records can be resolved by their processed index."""
        for i in range(3):
            original = response_with_annotations.resolve_extracted_record(i)
            assert original is not None
            assert original[DataExtractor.EXTRACTION_INDEX_KEY] == i

    def test_returns_none_for_invalid_index(self, response_with_annotations):
        """Verify None returned for out-of-bounds indices."""
        assert response_with_annotations.resolve_extracted_record(-1) is None
        assert response_with_annotations.resolve_extracted_record(100) is None

    def test_returns_none_when_no_records(self):
        """Verify None returned when processed_records or extracted_records missing."""
        response = ProcessedResponse(processed_records=None, extracted_records=None)
        assert response.resolve_extracted_record(0) is None

        response = ProcessedResponse(
            processed_records=[{"title": "Test"}],
            extracted_records=None,
        )
        assert response.resolve_extracted_record(0) is None

    def test_validates_record_id_by_default(self, response_with_annotations):
        """Verify ID validation catches mismatches when validate_id=True."""
        # Corrupt the extracted records to create a mismatch
        response_with_annotations.extracted_records[0][DataExtractor.RECORD_ID_KEY] = "corrupted_id"

        # With validation (default), should fallback to ID search and fail
        original = response_with_annotations.resolve_extracted_record(0)
        # Fallback search won't find "abc123def456_0" since we corrupted it
        assert original is None

    def test_skips_validation_when_disabled(self, response_with_annotations):
        """Verify index-only resolution when validate_id=False."""
        # Corrupt the ID - with validation disabled, should still return by index
        response_with_annotations.extracted_records[0][DataExtractor.RECORD_ID_KEY] = "corrupted_id"

        original = response_with_annotations.resolve_extracted_record(0, validate_id=False)
        assert original is not None
        assert original["title"] == "Machine Learning in Healthcare"

    def test_fallback_to_id_search_when_index_invalid(self, sample_extracted_records, sample_processed_records):
        """Verify O(n) fallback search when index-based lookup fails."""
        # Simulate reordering: processed records in different order than extracted
        reordered_processed = [
            sample_processed_records[2],  # Was index 2
            sample_processed_records[0],  # Was index 0
            sample_processed_records[1],  # Was index 1
        ]

        response = ProcessedResponse(
            extracted_records=sample_extracted_records,
            processed_records=reordered_processed,
            response=ReconstructedResponse.build(status_code=200, url="https://api.example.com"),
        )

        # Index 0 in processed has _extraction_index=2, but ID validation will fail
        # Fallback should find correct record by _record_id
        original = response.resolve_extracted_record(0)
        assert original is not None
        assert original["title"] == "Reinforcement Learning Survey"  # The one at processed[0]

    def test_no_fallback_when_disabled(self, sample_extracted_records, sample_processed_records):
        """Verify no fallback search when fallback_to_id_search=False."""
        # Create mismatch scenario
        reordered_processed = [
            record | {DataExtractor.EXTRACTION_INDEX_KEY: len(record) - record[DataExtractor.EXTRACTION_INDEX_KEY] - 1}
            for record in sample_processed_records
        ]

        response = ProcessedResponse(
            extracted_records=sample_extracted_records,
            processed_records=reordered_processed,
        )

        # With fallback disabled, should return None when index doesn't match
        original = response.resolve_extracted_record(0, fallback_to_id_search=False)
        # Index lookup finds wrong record, validation fails, no fallback -> None
        assert original is None

    def test_returns_none_without_annotation_fields(self, response_without_annotations):
        """Verify None returned when records lack annotation fields."""
        original = response_without_annotations.resolve_extracted_record(0)
        # No _extraction_index in processed records, so resolution fails
        assert original is None


# =============================================================================
# _resolve_by_record_id Tests
# =============================================================================


class TestResolveByRecordId:
    """Tests for ProcessedResponse._resolve_by_record_id()."""

    def test_finds_record_by_id(self, response_with_annotations):
        """Verify linear search finds correct record."""
        original = response_with_annotations._resolve_by_record_id("def456abc789_1")

        assert original is not None
        assert original["title"] == "Deep Learning for NLP"

    def test_returns_none_for_unknown_id(self, response_with_annotations):
        """Verify None returned for non-existent ID."""
        assert response_with_annotations._resolve_by_record_id("nonexistent_id") is None

    def test_returns_none_when_no_extracted_records(self):
        """Verify None returned when extracted_records is empty."""
        response = ProcessedResponse(extracted_records=None)
        assert response._resolve_by_record_id("any_id") is None


# =============================================================================
# strip_annotations Tests
# =============================================================================


class TestStripAnnotations:
    """Tests for ProcessedResponse.strip_annotations()."""

    def test_removes_annotation_fields(self, response_with_annotations):
        """Verify internal fields are stripped from records."""
        clean = response_with_annotations.strip_annotations()

        assert len(clean) == 3
        for record in clean:
            assert DataExtractor.EXTRACTION_INDEX_KEY not in record
            assert DataExtractor.RECORD_ID_KEY not in record

    def test_preserves_non_annotation_fields(self, response_with_annotations):
        """Verify regular fields are preserved after stripping."""
        clean = response_with_annotations.strip_annotations()

        assert clean[0]["title"] == "Machine Learning in Healthcare"
        assert clean[0]["author.name"] == "Smith"
        assert clean[1]["metadata.doi"] == "10.1234/dl.2024.002"

    def test_returns_new_list(self, response_with_annotations):
        """Verify strip_annotations returns a new list, not mutating original."""
        original_records = response_with_annotations.processed_records
        clean = response_with_annotations.strip_annotations()

        # Original should still have annotations
        assert DataExtractor.EXTRACTION_INDEX_KEY in original_records[0]
        assert DataExtractor.RECORD_ID_KEY in original_records[0]

        # Clean should not
        assert DataExtractor.EXTRACTION_INDEX_KEY not in clean[0]

    def test_accepts_custom_records(self, response_with_annotations):
        """Verify custom records can be passed for stripping."""
        custom_records = [
            {"_custom_field": "value", "_record_id": "id", "title": "Test"},
        ]
        clean = response_with_annotations.strip_annotations(records=custom_records)

        assert len(clean) == 1
        assert "_custom_field" not in clean[0]
        assert "_record_id" not in clean[0]
        assert clean[0]["title"] == "Test"

    def test_returns_empty_list_when_no_records(self):
        """Verify empty list returned when no records available."""
        response = ProcessedResponse(processed_records=None)
        assert response.strip_annotations() == []

        response = ProcessedResponse(processed_records=[])
        assert response.strip_annotations() == []

    def test_handles_mixed_key_types(self):
        """Verify integer keys (from XML parsing) are preserved."""
        records: list[dict] = [
            {0: "xml_value", "_annotation": "strip", "title": "Keep"},
        ]
        response = ProcessedResponse(processed_records=records)
        clean = response.strip_annotations()

        assert 0 in clean[0]  # Integer key preserved
        assert "_annotation" not in clean[0]  # String underscore key stripped
        assert clean[0]["title"] == "Keep"


# =============================================================================
# _prepare_normalization_records Tests
# =============================================================================


class TestPrepareNormalizationRecords:
    """Tests for ProcessedResponse._prepare_normalization_records()."""

    def test_merges_when_annotations_present(self, response_with_annotations):
        """Verify extracted and processed records are merged when annotations exist."""
        merged = response_with_annotations._prepare_normalization_records()

        assert merged is not None
        assert len(merged) == 3

        # Should have both nested (from extracted) and flattened (from processed) fields
        first = merged[0]
        assert first["author"]["name"] == "Smith"  # Nested from extracted
        assert first["author.name"] == "Smith"  # Flattened from processed

    def test_does_not_merge_when_resolve_records_false(self, response_with_annotations):
        """Verifies that `processed_records` is returned when using `resolve_records=False`."""
        processed_records = response_with_annotations._prepare_normalization_records(resolve_records=False)

        assert processed_records is response_with_annotations.processed_records

    def test_does_not_merge_with_nonstring_id_annotations(self, response_with_nonstring_id_annotations):
        """Verifies that `processed_records` is returned when the ID dictionary is empty due to non-string ID types."""
        processed_records = response_with_nonstring_id_annotations._prepare_normalization_records()

        assert processed_records is response_with_nonstring_id_annotations.processed_records

    def test_does_not_merge_with_nonmatching_annotations(self, response_with_nonmatching_annotations):
        """Verifies that `processed_records` is returned when annotations don't match."""
        processed_records = response_with_nonmatching_annotations._prepare_normalization_records()

        assert processed_records == response_with_nonmatching_annotations.processed_records

    def test_returns_processed_when_no_annotations(self, response_without_annotations):
        """Verify processed_records returned unchanged when no annotations."""
        result = response_without_annotations._prepare_normalization_records()

        # Should be the same object (no merge performed)
        assert result is response_without_annotations.processed_records

    def test_returns_processed_when_no_extracted_records(self, sample_processed_records):
        """Verify processed_records returned when extracted_records missing."""
        response = ProcessedResponse(
            extracted_records=None,
            processed_records=sample_processed_records,
        )
        result = response._prepare_normalization_records()

        assert result is response.processed_records

    def test_returns_extracted_when_no_processed_records(self, sample_extracted_records):
        """Verifies that `extracted_records` is returned when processed_records missing."""
        response = ProcessedResponse(
            extracted_records=sample_extracted_records,
            processed_records=None,
        )
        result = response._prepare_normalization_records()

        assert result is response.extracted_records

    def test_returns_none_on_empty_records(self, sample_extracted_records):
        """Verify None returned when processed_records missing."""
        response = ProcessedResponse(
            extracted_records=None,
            processed_records=None,
        )
        result = response._prepare_normalization_records()

        assert result is None

    def test_processed_fields_override_extracted(self, response_with_annotations):
        """Verify processed fields take precedence in merge (extracted | processed)."""
        # Modify a processed record to have different value
        response_with_annotations.processed_records[0]["title"] = "Modified Title"

        merged = response_with_annotations._prepare_normalization_records()

        # Processed value should win
        assert merged[0]["title"] == "Modified Title"


# =============================================================================
# _merge_record_pair Tests
# =============================================================================


class TestMergeRecordPair:
    """Tests for ProcessedResponse._merge_record_pair()."""

    def test_merges_extracted_and_processed(self, response_with_annotations):
        """Verify correct merge semantics (extracted | processed)."""
        id_index = response_with_annotations.build_record_id_index()
        processed = response_with_annotations.processed_records[0]

        merged = response_with_annotations._merge_record_pair(processed, id_index)

        # Should have nested structure from extracted
        assert "author" in merged
        assert merged["author"]["affiliation"]["department"] == "CSAIL"

        # Should have flattened fields from processed
        assert merged["author.name"] == "Smith"

    def test_returns_processed_when_no_match(self, response_with_annotations):
        """Verify processed record returned when no matching extracted record."""
        id_index = response_with_annotations.build_record_id_index()
        unmatched = {DataExtractor.RECORD_ID_KEY: "unknown_id", "title": "Orphan"}

        result = response_with_annotations._merge_record_pair(unmatched, id_index)

        assert result is unmatched

    def test_returns_processed_when_no_record_id(self, response_with_annotations):
        """Verify processed record returned when _record_id missing or invalid."""
        id_index = response_with_annotations.build_record_id_index()

        # Missing _record_id
        no_id = {"title": "No ID"}
        assert response_with_annotations._merge_record_pair(no_id, id_index) is no_id

        # Non-string _record_id
        bad_id = {DataExtractor.RECORD_ID_KEY: 12345, "title": "Bad ID"}
        assert response_with_annotations._merge_record_pair(bad_id, id_index) is bad_id


# =============================================================================
# Integration Tests
# =============================================================================


class TestRecordResolutionIntegration:
    """End-to-end tests for record resolution workflows."""

    def test_full_resolution_workflow(self, sample_extracted_records, sample_processed_records):
        """Test complete workflow: extract → process → resolve → access nested data."""
        response = ProcessedResponse(
            extracted_records=sample_extracted_records,
            processed_records=sample_processed_records,
        )

        # Simulate user workflow: iterate processed, resolve when needed
        assert response.extracted_records and response.processed_records
        for i, processed in enumerate(response.processed_records):
            # User has flattened data
            assert isinstance(processed, dict) and "author.name" in processed

            # Resolve to get nested structure
            original = response.resolve_extracted_record(i)
            assert original is not None

            # Access nested data not in flattened record
            department = original["author"]["affiliation"]["department"]
            assert department in ("CSAIL", "NLP Lab", "BAIR")

    def test_batch_resolution_via_index(self, response_with_annotations):
        """Test efficient batch resolution using pre-built index."""
        id_index = response_with_annotations.build_record_id_index()

        # Batch lookup
        resolved = []
        for processed in response_with_annotations.processed_records:
            record_id = processed.get(DataExtractor.RECORD_ID_KEY)
            if record_id:
                resolved.append(id_index.get(record_id))

        assert len(resolved) == 3
        assert all(r is not None for r in resolved)

    def test_strip_for_dataframe_export(self, response_with_annotations):
        """Test stripping annotations for clean DataFrame creation."""
        clean_records = response_with_annotations.strip_annotations()

        # Simulate DataFrame creation (just verify structure)
        for record in clean_records:
            # No internal fields that would confuse DataFrame
            assert not any(k.startswith("_") for k in record if isinstance(k, str))

            # Data fields preserved
            assert "title" in record
            assert "author.name" in record

    def test_normalize_uses_merged_records(self, response_with_annotations):
        """Verify normalize() receives merged records when annotations present."""
        # Mock the field_map to capture what records it receives
        mock_field_map = MagicMock()
        mock_field_map.normalize_records.return_value = [{"normalized": True}]

        response_with_annotations.normalize(field_map=mock_field_map)

        # Verify normalize_records was called with merged data
        call_args = mock_field_map.normalize_records.call_args[0][0]

        # Merged records should have both nested and flattened fields
        assert "author" in call_args[0]  # Nested from extracted
        assert "author.name" in call_args[0]  # Flattened from processed

    def test_search_result_extracted_record_resolution_delegates_to_processed_response(
        self, sample_extracted_records, sample_processed_records
    ):
        """Tests whether `SearchResult.resolve_extracted_record` delegates resolution to the processed API Response."""
        mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
        response = ProcessedResponse(
            response=mock_response,
            extracted_records=sample_extracted_records,
            processed_records=sample_processed_records,
        )
        search_result = SearchResult(
            response_result=response, query="test_query", provider_name="mock_provider", page=1
        )
        assert all(
            search_result.resolve_extracted_record(record["_extraction_index"])
            == response.resolve_extracted_record(record["_extraction_index"])
            for record in response.processed_records or []
        )

    def test_search_result_build_record_id_index_delegates_to_processed_response(
        self, sample_extracted_records, sample_processed_records
    ):
        """Tests whether `SearchResult.build_record_id_index` delegates resolution to the processed API Response."""
        mock_response = ReconstructedResponse.build(status_code=200, url="https://non-existent-url.com")
        response = ProcessedResponse(
            response=mock_response,
            extracted_records=sample_extracted_records,
            processed_records=sample_processed_records,
        )
        search_result = SearchResult(
            response_result=response, query="test_query", provider_name="mock_provider", page=1
        )
        response_id_index = response.build_record_id_index()
        assert response_id_index and response_id_index == search_result.build_record_id_index()
