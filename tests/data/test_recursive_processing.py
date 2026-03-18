import pytest
from scholar_flux.data import RecursiveDataProcessor
from scholar_flux.exceptions import DataProcessingException, DataValidationException
from tests.testing_utilities import raise_error


def test_recursive_processor(sample_json, mock_api_parsed_json_records):
    """Verifies that the recursive processor processes, flattens, and filters json objects correctly.

    On the backend, a `RecursiveJsonProcessor` should first flatten the record while excluding the specified paths.

    Paths with keys that match the user-specified patterns should also be filtered as needed with the use of a custom
    KeyFilter to ensure that the processed data, when flattened, returns the expected, flattened record list.

    """
    processor = RecursiveDataProcessor(sample_json)
    assert isinstance(processor.json_data, list)
    processed = processor.process_page()
    assert isinstance(processed, list)
    assert all(isinstance(d, dict) for d in processed)

    discovered_keys = processor.discover_keys()
    filtered_keys_by_prefix = processor.filter_keys(prefix="address")
    filtered_keys_by_length = processor.filter_keys(min_length=3)
    filtered_keys_by_substring = processor.filter_keys(substring="state")

    flattened_process = (
        [processor.recursive_processor.process_and_flatten(data) for data in processor.json_data]
        if processor.json_data
        else None
    )
    assert flattened_process is not None and len(flattened_process) == 1
    processed_records = processor.process_page()

    assert discovered_keys
    assert filtered_keys_by_prefix
    assert filtered_keys_by_length
    assert filtered_keys_by_substring
    assert len(processed_records) == 1

    processed_records2 = processor.process_page(mock_api_parsed_json_records)
    assert processed_records2
    discovered_keys2 = processor.discover_keys()
    assert discovered_keys2 and discovered_keys != discovered_keys2


def test_recursive_processor_load_data(sample_json, caplog):
    """Verifies that the recursive processor correctly loads and indicates whether data has been loaded."""
    assert not RecursiveDataProcessor().load_data()

    assert RecursiveDataProcessor(sample_json).load_data()

    assert "Updating JSON data..." not in caplog.text
    assert "JSON data loaded" in caplog.text

    caplog.clear()
    assert RecursiveDataProcessor().load_data(sample_json)
    assert "JSON data loaded" in caplog.text


def test_recursive_processor_load_invalid_data(sample_json, caplog):
    """Verifies that the recursive processor raises a `DataValidationException` when invalid JSON data is received."""
    invalid_json_data = "Not a JSON"
    with pytest.raises(DataValidationException) as excinfo:
        _ = RecursiveDataProcessor(json_data=invalid_json_data)  # type: ignore
    err = "The JSON data could not be successfully loaded and processed"
    data_type_invalid = f"Expected a list of dictionary-based records but received type {type(invalid_json_data)}"

    assert f"{err}: {data_type_invalid}" in str(excinfo.value)

    invalid_json_list = ["Invalid json list"]
    with pytest.raises(DataValidationException) as excinfo:
        _ = RecursiveDataProcessor(json_data=invalid_json_list)  # type: ignore
    record_invalid = "Expected a list of dictionary-based records but at least one element in the JSON is invalid."
    assert f"{err}: {record_invalid}" in str(excinfo.value)


def test_unexpected_page_processing_error(mock_api_parsed_json_records, monkeypatch):
    """Verifies that the `RecursiveDataProcessor` raises a `DataProcessingException` on unexpected processing errors."""
    err = "Directly raised exception"
    monkeypatch.setattr(RecursiveDataProcessor, "process_record", raise_error(RuntimeError, err))

    processor = RecursiveDataProcessor()

    with pytest.raises(DataProcessingException, match=f"An unexpected error occurred during data processing: {err}"):
        _ = processor.process_page(mock_api_parsed_json_records)


def test_page_processing_with_empty_json_raises_error():
    """Verifies that a `DataValidationException` is raised on `process_page` when a json data set is not received."""
    processor = RecursiveDataProcessor()
    with pytest.raises(DataValidationException, match=r"A valid JSON dictionary could not be successfully loaded\."):
        _ = processor.process_page()


def test_process_page_with_json_traversal(mock_api_parsed_json_records):
    """Verifies that the `RecursiveJsonProcessor` can use a nested list of record keys to extract nested JSON records.

    The final processed record list should consist of two dictionaries containing fields mapping each full, period
    delimited path to the corresponding value found at that path.

    If the DataProcessor is ran once more on the processed page of records, the results should also be identical.

    """
    record_keys: list = [
        "authors.principle_investigator",
        "authors.assistant",
        "doi",
        "title",
        "genre.subspecialty",
        "journal.topic",
        "abstract",
        "affiliations",
    ]
    processor = RecursiveDataProcessor(value_delimiter=None)
    json_processor = processor.recursive_processor
    results: list[dict] = [
        json_processor.process_and_flatten(record, traversal_paths=record_keys)  # type: ignore
        for record in mock_api_parsed_json_records
    ]
    assert isinstance(results, list) and isinstance(results[0], dict) and isinstance(results[1], dict)
    assert results[0]["authors.principle_investigator"] == "Dr. Smith"
    assert results[1]["authors.assistant"] == "John Roe"
    assert isinstance(results[0]["abstract"], list)
    assert results[1]["abstract"] == "Another abstract."
    assert results[0]["affiliations"] == ["KSU", "LSU"]
    assert results[1]["affiliations"] == ["LSU"]

    # testing idempotence
    processed_results = processor.process_page(results)
    assert results == processed_results


def test_mixed_path_formats(mock_api_parsed_json_records):
    """Verifies that the `DataProcessor` accepts both string and list path formats for non-standard JSON structures."""

    # Mixed path formats
    record_keys: list = [
        "authors.principle_investigator",  # String format
        ["authors", "assistant"],  # List format
        ["doi"],  # Single element list
        "title",  # String format
        ["genre", "subspecialty"],  # List format
        "journal.topic",  # String format
        "abstract",
        "affiliations",
    ]

    processor = RecursiveDataProcessor(value_delimiter=None)
    json_processor = processor.recursive_processor

    results = [
        json_processor.process_and_flatten(record, traversal_paths=record_keys)
        for record in mock_api_parsed_json_records
    ]
    assert isinstance(results, (list))

    assert isinstance(results[0], dict) and results[0]["authors.principle_investigator"] == "Dr. Smith"
    assert isinstance(results[1], dict) and results[1]["authors.assistant"] == "John Roe"
    assert results[0]["affiliations"] == ["KSU", "LSU"]


def test_integer_path_indices():
    """Test explicit integer indices in paths for non-standard JSON structures."""

    # Non-standard JSON with numeric keys or requiring specific list access
    data = {
        "items": [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}, {"id": 3, "name": "Third"}],
        "metadata": {
            "0": "zero_key",  # String key that looks like number
            0: "int_key",  # Actual integer key (unusual but valid Python dict)
        },
    }

    processor = RecursiveDataProcessor(value_delimiter=None)
    json_processor = processor.recursive_processor

    # Test explicit list index access
    paths_with_indices: list[list[str | int]] = [
        ["items", 0, "name"],  # First item
        ["items", 1, "id"],  # Second item's id
        ["metadata", "0"],  # String "0" key
        ["metadata", 0],  # Integer 0 key
    ]

    result = json_processor.process_and_flatten(data, traversal_paths=paths_with_indices)
    assert isinstance(result, dict)

    assert result["items.name"] == "First"  # or however you want to flatten it
    assert result["items.id"] == 2
    assert "metadata.0" in result or "metadata" in result


def test_recursive_data_processor_loads_single_record_dictionary_into_list(mock_api_parsed_json_records):
    """Verifies that the `RecursiveDataProcessor` nests a single record into a list when received."""
    processor = RecursiveDataProcessor(mock_api_parsed_json_records[0])
    assert processor.json_data == mock_api_parsed_json_records[:1]


def test_processor_gracefully_handles_missing_record():
    """Verifies the edge case that `process_record` returns an empty dictionary when passed None."""
    processor = RecursiveDataProcessor()
    assert processor.process_record(None) == {}  # type: ignore


def test_processor_gracefully_processes_empty_record_list():
    """Verifies that an empty list is returned when the `RecursiveDataProcessor` processes an empty page."""
    processor = RecursiveDataProcessor(json_data=[])
    result = processor.process_page()
    assert result == []


def test_filter_keys(mock_api_parsed_json_records):
    """Validates that filtering keys works as intended when enabled."""
    # Base processing results:
    processor = RecursiveDataProcessor()
    base_results = processor.process_page(mock_api_parsed_json_records)

    # fixed-string matching
    n_records = len(mock_api_parsed_json_records)
    processor = RecursiveDataProcessor(keep_keys=["principle_investigator"], regex=False)
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == n_records
    assert results == base_results

    processor = RecursiveDataProcessor(keep_keys=["princip_invest"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0

    processor = RecursiveDataProcessor(ignore_keys=["non-existent-key"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == n_records
    assert results == base_results

    # regular expressions
    processor = RecursiveDataProcessor(keep_keys=["principle.*"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == n_records

    processor = RecursiveDataProcessor(ignore_keys=["principle.*"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0
