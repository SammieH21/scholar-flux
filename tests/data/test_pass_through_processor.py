import pytest
from scholar_flux.data import PassThroughDataProcessor
from scholar_flux.exceptions import DataProcessingException


def test_process_page(mock_api_parsed_json_records):

    processor = PassThroughDataProcessor()
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == 2
    assert mock_api_parsed_json_records == results


def test_filter_keys(mock_api_parsed_json_records):

    processor = PassThroughDataProcessor(keep_keys=["principle_investigator"], regex=False)
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == 2
    assert results == mock_api_parsed_json_records

    processor = PassThroughDataProcessor(keep_keys=["princip_invest"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0

    processor = PassThroughDataProcessor(ignore_keys=["non-existent-key"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == 2
    assert results == mock_api_parsed_json_records

    processor = PassThroughDataProcessor(ignore_keys=["principle.*"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0


##### edge cases ######


def test_blank_record_keys(mock_api_parsed_json_records):
    processor = PassThroughDataProcessor(keep_keys=[""])
    results = processor.process_page(mock_api_parsed_json_records)
    assert not results

    processor = PassThroughDataProcessor(ignore_keys=[""])
    results = processor.process_page(mock_api_parsed_json_records)
    assert results == mock_api_parsed_json_records


def test_invalid_record_keys_type_raises():
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
    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor._validate_inputs("not a list or dict either", None, True)  # type:ignore
    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor._validate_inputs("not a list", "not a list either", False)  # type:ignore
    with pytest.raises(DataProcessingException):
        PassThroughDataProcessor._validate_inputs(None, None, 123)  # type:ignore
