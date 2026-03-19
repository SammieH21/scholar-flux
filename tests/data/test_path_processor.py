import pytest
from scholar_flux.data import PathDataProcessor
from scholar_flux.exceptions import DataProcessingException, DataValidationException
from tests.testing_utilities import raise_error


def test_path_data_processor(sample_json):
    """Verifies that the recursive data processor correctly filters keys as required.

    The data processor should use a custom KeyFilter to ensure that the processed data, when flattened, will return the
    expected, flattened set of records.

    """
    processor = PathDataProcessor(sample_json)
    assert isinstance(processor.json_data, list)
    processed = processor.process_page()
    assert isinstance(processed, list)
    assert all(isinstance(d, dict) for d in processed)
    assert processor.cached
    discovered_keys = processor.discover_keys()
    assert isinstance(discovered_keys, dict) and all(isinstance(key, (str)) for key in discovered_keys)

    processed_records = processor.process_page()

    assert isinstance(processed_records, list) and all(
        isinstance(record, dict) and all(isinstance(key, str) for key in record) for record in processed_records
    )

    records_kept = processor.process_page(keep_keys=["n.me"], regex=True)
    assert records_kept == processed_records

    records_removed = processor.process_page(ignore_keys=["name"])
    assert records_kept != records_removed


def test_path_processor_load_data(sample_json, caplog):
    """Verifies that the path data processor correctly loads and indicates whether data has been loaded."""
    assert not PathDataProcessor().load_data()

    assert PathDataProcessor(sample_json).load_data()

    assert "Updating JSON data..." not in caplog.text
    assert "JSON data loaded" in caplog.text

    caplog.clear()
    assert PathDataProcessor().load_data(sample_json)
    assert "Updating JSON data..." not in caplog.text
    assert "JSON data loaded" in caplog.text


def test_path_processor_updates_data_on_load(sample_json, mock_api_parsed_json_records, caplog):
    """Verifies that the PathDataProcessor correctly updates the loaded JSON data when provided via `load_data`."""
    assert not PathDataProcessor().load_data()

    processor = PathDataProcessor(sample_json)
    assert processor.json_data == sample_json

    assert processor.load_data(mock_api_parsed_json_records)
    assert processor.json_data == mock_api_parsed_json_records

    assert "Updating JSON data..." in caplog.text
    assert "JSON data loaded" in caplog.text


def test_path_data_processor_loads_single_record_dictionary_into_list(mock_api_parsed_json_records):
    """Verifies that the PathDataProcessor nests a single record into a list when received."""
    processor = PathDataProcessor(mock_api_parsed_json_records[0])
    assert processor.json_data == mock_api_parsed_json_records[:1]


def test_processor_gracefully_processes_empty_record_list():
    """Verifies that an empty list is returned when the PathDataProcessor processes an empty page."""
    processor = PathDataProcessor(json_data=[])
    result = processor.process_page()
    assert result == []


def test_path_data_processor_gracefully_handles_incorrect_index(mock_api_parsed_json_records, caplog):
    """Verifies that `process_record` gracefully handles numeric indexes that cannot be found in the PathNodeIndex."""
    processor = PathDataProcessor(mock_api_parsed_json_records)
    assert processor()  # calls `process_page` under the hood

    missing_index = 10
    processor.process_record(record_index=missing_index)
    assert f"A record is not associated with the following index: {missing_index}" in caplog.text


def test_path_data_processor_load_invalid_data(sample_json, caplog):
    """Verifies that the path data processor raises a DataValidationException when invalid JSON data is received."""
    invalid_json_data = "Not a valid data type"
    with pytest.raises(DataValidationException) as excinfo:
        _ = PathDataProcessor(json_data=invalid_json_data)  # type: ignore

    assert "The JSON data could not be successfully loaded and processed into an index: " in str(excinfo.value)


def test_unexpected_page_processing_error(mock_api_parsed_json_records, monkeypatch):
    """Verifies that the PathDataProcessor raises a DataProcessingException on unexpected processing errors."""
    err = "Directly raised exception"
    monkeypatch.setattr(PathDataProcessor, "process_record", raise_error(RuntimeError, err))

    processor = PathDataProcessor()

    with pytest.raises(DataProcessingException, match=f"An unexpected error occurred during data processing: {err}"):
        _ = processor.process_page(mock_api_parsed_json_records)


def test_page_processing_with_empty_json_raises_error():
    """Verifies that a `DataValidationException` is raised on `process_page` when a json data set is not received."""
    processor = PathDataProcessor()

    with pytest.raises(
        DataValidationException, match="JSON data could not be successfully loaded into the JSON processing index."
    ):
        _ = processor.process_page()
