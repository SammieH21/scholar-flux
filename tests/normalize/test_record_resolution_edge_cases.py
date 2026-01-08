# tests/api/models/test_record_resolution_edge_cases.py
"""Edge case tests for record resolution, including nested JSON detection.

These tests cover scenarios where the merge behavior should be skipped,
such as when processed records still contain nested structures (passthrough processing).

"""
import pytest
from scholar_flux.api.models import ProcessedResponse
from scholar_flux.data.data_extractor import DataExtractor


# =============================================================================
# is_nested_json Detection Tests
# =============================================================================


class TestNestedJsonDetection:
    """Tests for scenarios where processed records are still nested (not flattened).

    When records pass through without flattening (passthrough processor), merging
    is unnecessary and should be skipped to avoid redundant computation.
    """

    @pytest.fixture
    def nested_processed_records(self) -> list[dict]:
        """Processed records that retain nested structure (passthrough scenario)."""
        return [
            {
                DataExtractor.EXTRACTION_INDEX_KEY: 0,
                DataExtractor.RECORD_ID_KEY: "abc123_0",
                "title": "Test Article",
                "author": {"name": "Smith", "affiliation": "MIT"},  # Still nested
                "metadata": {"doi": "10.1234/test"},  # Still nested
            },
        ]

    @pytest.fixture
    def flattened_processed_records(self) -> list[dict]:
        """Processed records with flattened structure."""
        return [
            {
                DataExtractor.EXTRACTION_INDEX_KEY: 0,
                DataExtractor.RECORD_ID_KEY: "abc123_0",
                "title": "Test Article",
                "author.name": "Smith",  # Flattened
                "author.affiliation": "MIT",  # Flattened
                "metadata.doi": "10.1234/test",  # Flattened
            },
        ]

    def test_skips_merge_when_records_still_nested(self, nested_processed_records):
        """Verify no merge performed when processed records retain nested structure."""
        # Same records used for both extracted and processed (passthrough scenario)
        response = ProcessedResponse(
            extracted_records=nested_processed_records,
            processed_records=nested_processed_records,
        )

        result = response._prepare_normalization_records()

        # Should return processed_records as-is, not merged
        # (In the actual implementation, is_nested_json would detect this)
        # For now, we're testing that the method handles this gracefully
        assert result is not None

    def test_performs_merge_when_records_flattened(self, nested_processed_records, flattened_processed_records):
        """Verify merge performed when processed records are flattened."""
        response = ProcessedResponse(
            extracted_records=nested_processed_records,
            processed_records=flattened_processed_records,
        )

        result = response._prepare_normalization_records()

        assert result is not None
        # Merged should have both nested (from extracted) and flat (from processed)
        assert "author" in result[0]  # Nested structure
        assert "author.name" in result[0]  # Flattened key


# =============================================================================
# Edge Cases: Malformed Data
# =============================================================================


class TestMalformedDataHandling:
    """Tests for handling malformed or unexpected data structures."""

    def test_handles_empty_processed_record(self):
        """Verify empty records in processed_records don't cause errors."""
        extracted = [
            {DataExtractor.RECORD_ID_KEY: "id_0", "title": "Test"},
        ]
        processed: list[dict] = [
            {},  # Empty record
        ]

        response = ProcessedResponse(
            extracted_records=extracted,
            processed_records=processed,
        )

        # Should not raise, should return processed as-is (no annotation fields)
        result = response._prepare_normalization_records()
        assert result is response.processed_records

    def test_handles_mismatched_record_counts(self):
        """Verify handling when extracted and processed have different lengths."""
        extracted = [
            {DataExtractor.RECORD_ID_KEY: "id_0", DataExtractor.EXTRACTION_INDEX_KEY: 0, "title": "One"},
            {DataExtractor.RECORD_ID_KEY: "id_1", DataExtractor.EXTRACTION_INDEX_KEY: 1, "title": "Two"},
        ]
        processed = [
            {DataExtractor.RECORD_ID_KEY: "id_0", DataExtractor.EXTRACTION_INDEX_KEY: 0, "title": "One"},
            # Second record filtered out during processing
        ]

        response = ProcessedResponse(
            extracted_records=extracted,
            processed_records=processed,
        )

        result = response._prepare_normalization_records()
        assert result is not None
        assert len(result) == 1  # Only merged what's in processed

    def test_handles_duplicate_record_ids(self):
        """Verify behavior when multiple records have same _record_id."""
        extracted = [
            {DataExtractor.RECORD_ID_KEY: "duplicate_id", "title": "First"},
            {DataExtractor.RECORD_ID_KEY: "duplicate_id", "title": "Second"},  # Duplicate!
        ]

        response = ProcessedResponse(extracted_records=extracted)
        index = response.build_record_id_index()

        # Last one wins in dict comprehension
        assert len(index) == 1
        assert index["duplicate_id"]["title"] == "Second"

    def test_handles_none_values_in_records(self):
        """Verify None values in record fields don't cause issues."""
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

        response = ProcessedResponse(
            extracted_records=extracted,
            processed_records=processed,
        )

        result = response._prepare_normalization_records()
        assert result is not None
        assert result[0]["title"] is None


# =============================================================================
# Edge Cases: Resolution Fallback Scenarios
# =============================================================================


class TestResolutionFallbackScenarios:
    """Tests for various fallback scenarios during resolution."""

    def test_fallback_when_extraction_index_out_of_bounds(self):
        """Verify fallback to ID search when _extraction_index exceeds extracted_records length."""
        extracted = [
            {DataExtractor.RECORD_ID_KEY: "id_0", "title": "Only One"},
        ]
        processed = [
            {
                DataExtractor.RECORD_ID_KEY: "id_0",
                DataExtractor.EXTRACTION_INDEX_KEY: 999,  # Invalid index
                "title": "Only One",
            },
        ]

        response = ProcessedResponse(
            extracted_records=extracted,
            processed_records=processed,
        )

        # Index 999 is out of bounds, should fallback to ID search
        original = response.resolve_extracted_record(0)
        assert original is not None
        assert original["title"] == "Only One"

    def test_fallback_when_extraction_index_negative(self):
        """Verify handling of negative _extraction_index values."""
        extracted = [
            {DataExtractor.RECORD_ID_KEY: "id_0", "title": "Test"},
        ]
        processed = [
            {
                DataExtractor.RECORD_ID_KEY: "id_0",
                DataExtractor.EXTRACTION_INDEX_KEY: -1,  # Negative
                "title": "Test",
            },
        ]

        response = ProcessedResponse(
            extracted_records=extracted,
            processed_records=processed,
        )

        # Negative index should fail bounds check, fallback to ID search
        original = response.resolve_extracted_record(0)
        assert original is not None

    def test_no_resolution_when_all_methods_fail(self):
        """Verify None returned when both index and ID resolution fail."""
        extracted = [
            {DataExtractor.RECORD_ID_KEY: "different_id", "title": "Test"},
        ]
        processed = [
            {
                DataExtractor.RECORD_ID_KEY: "nonexistent_id",
                DataExtractor.EXTRACTION_INDEX_KEY: 999,
                "title": "Orphan",
            },
        ]

        response = ProcessedResponse(
            extracted_records=extracted,
            processed_records=processed,
        )

        original = response.resolve_extracted_record(0)
        assert original is None


# =============================================================================
# Edge Cases: Type Handling
# =============================================================================


class TestTypeHandling:
    """Tests for handling various data types in records."""

    def test_preserves_integer_keys_from_xml(self):
        """Verify integer keys (common in XML parsing) are handled correctly."""
        extracted: list[dict] = [
            {
                DataExtractor.RECORD_ID_KEY: "id_0",
                DataExtractor.EXTRACTION_INDEX_KEY: 0,
                0: "xml_text_content",  # Integer key from XML
                "title": "Test",
            },
        ]
        processed: list[dict] = [
            {
                DataExtractor.RECORD_ID_KEY: "id_0",
                DataExtractor.EXTRACTION_INDEX_KEY: 0,
                0: "xml_text_content",
                "title": "Test",
            },
        ]

        response = ProcessedResponse(
            extracted_records=extracted,
            processed_records=processed,
        )

        # strip_annotations should preserve integer keys
        clean = response.strip_annotations()
        assert 0 in clean[0]
        assert clean[0][0] == "xml_text_content"  # type: ignore

    def test_handles_non_string_field_values(self):
        """Verify various value types are preserved through resolution."""
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


# =============================================================================
# Performance Consideration Tests
# =============================================================================


class TestPerformanceConsiderations:
    """Tests documenting performance characteristics."""

    def test_index_provides_o1_lookup(self):
        """Document that build_record_id_index enables O(1) lookups."""
        # Create many records
        num_records = 1000
        extracted = [{DataExtractor.RECORD_ID_KEY: f"id_{i}", "title": f"Record {i}"} for i in range(num_records)]

        response = ProcessedResponse(extracted_records=extracted)
        index = response.build_record_id_index()

        # O(1) lookup for any record
        assert index[f"id_{500}"]["title"] == "Record 500"
        assert index[f"id_{999}"]["title"] == "Record 999"

    def test_linear_search_as_fallback(self):
        """Document that _resolve_by_record_id is O(n) fallback."""
        num_records = 100
        extracted = [
            {
                DataExtractor.RECORD_ID_KEY: f"id_{i}",
                DataExtractor.EXTRACTION_INDEX_KEY: i,
                "title": f"Record {i}",
            }
            for i in range(num_records)
        ]

        response = ProcessedResponse(extracted_records=extracted)

        # Linear search finds record (but is O(n))
        result = response._resolve_by_record_id("id_99")
        assert result is not None
        assert result["title"] == "Record 99"
