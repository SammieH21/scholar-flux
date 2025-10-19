import pytest
from scholar_flux.data import PassThroughDataProcessor
from scholar_flux.exceptions import DataProcessingException


def test_process_page(mock_api_parsed_json_records):
    """Validates that valid records ran through the PassThroughDataProcessor are returned as is."""
    processor = PassThroughDataProcessor()
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == len(mock_api_parsed_json_records)
    assert mock_api_parsed_json_records == results


def test_filter_keys(mock_api_parsed_json_records):
    """Validates that filtering keys works as intended when enabled There are two records in the
    mock_api_parsed_json_records, both of which have the `principle_investigator` key, so both records should be
    retained as is.

    Other keys such as `princip_invest` and `non-existent-key` should not be present.

    This test also validates with regular expressions which should work as intended with `regex=True`.
    """
    # fixed-string matching
    n_records = len(mock_api_parsed_json_records)
    processor = PassThroughDataProcessor(keep_keys=["principle_investigator"], regex=False)
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == n_records
    assert results == mock_api_parsed_json_records

    processor = PassThroughDataProcessor(keep_keys=["princip_invest"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0

    processor = PassThroughDataProcessor(ignore_keys=["non-existent-key"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == n_records
    assert results == mock_api_parsed_json_records

    # regular expressions
    processor = PassThroughDataProcessor(keep_keys=["principle.*"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == n_records

    processor = PassThroughDataProcessor(ignore_keys=["principle.*"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0


##### edge cases ######
def test_blank_record_keys(mock_api_parsed_json_records):
    """Validates whether an attempt to retain keys that are blank results in an empty record as expected.

    Ignoring a blank key should, by contrast, retain all records (since
    no keys should match key == "").
    """
    processor = PassThroughDataProcessor(keep_keys=[""])
    results = processor.process_page(mock_api_parsed_json_records)
    assert not results

    processor = PassThroughDataProcessor(ignore_keys=[""])
    results = processor.process_page(mock_api_parsed_json_records)
    assert results == mock_api_parsed_json_records


def test_invalid_record_keys_type_raises():
    """Validates that the inputs to the PassThroughDataProcessor raise an error when encountering invalid values that
    are validated during instantiation and processing."""
    data: list[dict] = [{}]
    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor(ignore_keys="not a list of strings")  # type:ignore

    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor(keep_keys="not a list of strings")  # type:ignore

    with pytest.raises(DataProcessingException):
        processor = PassThroughDataProcessor()  # type:ignore
        processor(data, regex="A")  # type:ignore

    with pytest.raises(DataProcessingException):
        processor = PassThroughDataProcessor()  # type:ignore
        processor(data, keep_keys="A")  # type:ignore

    with pytest.raises(DataProcessingException):
        processor = PassThroughDataProcessor()  # type:ignore
        processor(data, ignore_keys="A")  # type:ignore


def test_validate_inputs_with_invalid_types():
    """Verifies that validated inputs similarly raise a DataProcessingException when encountering invalid values that
    are checked during instantiation via the `_validate_inputs` method."""
    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor._validate_inputs("not a list or dict either", None, True)  # type:ignore
    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor._validate_inputs("not a list", "not a list either", False)  # type:ignore
    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor._validate_inputs(None, None, 123)  # type:ignore
