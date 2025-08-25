import pytest
from scholar_flux.data import DataProcessor
from scholar_flux.exceptions import DataProcessingException

def test_process_page_with_list_of_paths(mock_api_parsed_json_records):
    record_keys = [
        ["authors", "principle_investigator"],
        ["authors", "assistant"],
        ["doi"],
        ["title"],
        ["genre", "subspecialty"],
        ["journal", "topic"],
        ["abstract"]
    ]
    processor = DataProcessor(record_keys=record_keys, value_delimiter=None)
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == 2
    assert results[0]["authors.principle_investigator"] == "Dr. Smith"
    assert results[1]["authors.assistant"] == "John Roe"
    assert isinstance(results[0]["abstract"], list)
    assert results[1]["abstract"] == "Another abstract."

def test_process_page_with_dict_keys(mock_api_parsed_json_records):
    record_keys = {
        "pi": ["authors", "principle_investigator"],
        "assistant": ["authors", "assistant"],
        "doi": ["doi"],
        "title": ["title"],
        "subspecialty": ["genre", "subspecialty"],
        "topic": ["journal", "topic"],
        "abstract": ["abstract"]
    }
    processor = DataProcessor(record_keys=record_keys, value_delimiter=None)
    results = processor.process_page(mock_api_parsed_json_records)
    assert results[0]["pi"] == "Dr. Smith"
    assert results[1]["assistant"] == "John Roe"
    assert isinstance(results[0]["abstract"], list)
    assert results[1]["abstract"] == "Another abstract."

def test_value_delimiter_joins_lists(mock_api_parsed_json_records):
    record_keys = [["abstract"]]
    processor = DataProcessor(record_keys=record_keys, value_delimiter=" | ")
    results = processor.process_page(mock_api_parsed_json_records)
    assert results[0]["abstract"] == "This is a sample abstract. | keywords: 'sample', 'abstract'"
    assert results[1]["abstract"] == "Another abstract."


##### edge cases ######

def test_empty_record_keys_returns_empty_dict(mock_api_parsed_json_records):
    processor = DataProcessor(record_keys=[])
    results = processor.process_page(mock_api_parsed_json_records)
    assert all(result == {} for result in results)

def test_empty_input_list_returns_empty_list():
    processor = DataProcessor(record_keys=[["title"]])
    results = processor.process_page([])
    assert results == []

def test_missing_path_returns_none():
    processor = DataProcessor(record_keys=[["not", "present"]])
    results = processor.process_page([{"foo": "bar"}])
    assert results[0]["not.present"] is None

def test_integer_index_in_path():
    data = [{"a": [{"b": "val1"}, {"b": "val2"}]}]
    processor = DataProcessor(record_keys=[["a", 1, "b"]])
    results = processor.process_page(data)
    assert results[0]["a.1.b"] == "val2"

def test_non_string_values_are_handled():
    data = [{"num": 123, "lst": [1, 2, 3]}]
    processor = DataProcessor(record_keys=[["num"], ["lst"]], value_delimiter="|")
    results = processor.process_page(data)
    assert results[0]["num"] == 123
    assert results[0]["lst"] == "1|2|3"

def test_none_values_are_handled():
    data = [{"foo": None}]
    processor = DataProcessor(record_keys=[["foo"]])
    results = processor.process_page(data)
    assert results[0]["foo"] is None

def test_empty_dict_in_record():
    data = [{}]
    processor = DataProcessor(record_keys=[["foo"]])
    results = processor.process_page(data)
    assert results[0]["foo"] is None

def test_path_with_only_integers():
    data = [[{"bar": "baz"}], [{"bar": "qux"}]]
    processor = DataProcessor(record_keys=[[0, "bar"]])
    results = processor.process_page(data)
    assert results[0]["0.bar"] == "baz"
    assert results[1]["0.bar"] == "qux"

def test_record_filter_with_regex():
    data = [{"foo": "bar"}, {"baz": "qux"}]
    processor = DataProcessor(record_keys=[["foo"]])
    # Should filter out the first record if ignore_keys is ["foo"]
    results = processor.process_page(data, ignore_keys=["foo"])
    assert len(results) == 1
    assert "baz" not in results[0]

def test_invalid_record_keys_type_raises():
    with pytest.raises(DataProcessingException):
        DataProcessor(record_keys="not a list or dict")
def test_extract_key_returns_none_for_missing_key():
    record = {"foo": "bar"}
    assert DataProcessor.extract_key(record, "missing") is None

def test_extract_key_with_path():
    record = {"a": {"b": {"c": [1, 2, 3]}}}
    assert DataProcessor.extract_key(record, "c", ["a", "b"]) == [1, 2, 3]

def test_prepare_record_keys_with_invalid_type():
    with pytest.raises(DataProcessingException):
        DataProcessor._prepare_record_keys("not a list or dict")

def test_validate_inputs_with_invalid_types():
    with pytest.raises(DataProcessingException):
        DataProcessor._validate_inputs("not a list or dict", "not a list or dict either", None, ";")
    with pytest.raises(DataProcessingException):
        DataProcessor._validate_inputs([["a"]], "not a list", "not a list either", ";")
    with pytest.raises(DataProcessingException):
        DataProcessor._validate_inputs([["a"]], None, None, 123)

def test_collapse_fields_behavior():
    processor = DataProcessor(record_keys=[["foo"]], value_delimiter=";")
    data = {"foo": ["a", "b"]}
    collapsed = processor.collapse_fields({"foo": ["a", "b"]})
    assert collapsed["foo"] == "a;b"
    processor.value_delimiter = None
    collapsed = processor.collapse_fields({"foo": ["a", "b"]})
    assert collapsed["foo"] == ["a", "b"]

def test_record_filter_regex(mock_api_parsed_json_records):
    processor = DataProcessor(record_keys=[["title"]])
    # Should not filter out any records if ignore_keys is empty
    assert all(not processor.record_filter(rec) for rec in mock_api_parsed_json_records)
    # Should filter out records with "title" key
    assert all(processor.record_filter(rec, record_keys=["title"]) for rec in mock_api_parsed_json_records)


