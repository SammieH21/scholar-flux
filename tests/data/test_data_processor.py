import pytest
from scholar_flux.data import DataProcessor
from scholar_flux.exceptions import DataProcessingException


def test_process_page_with_list_of_paths(mock_api_parsed_json_records):
    """
    Verifies that each dictionary record with nested components in a list of records is successfully and
    dynamically flattened into the full nested path and corresponding value found at that path.
    """
    record_keys: list = [
        ["authors", "principle_investigator"],
        ["authors", "assistant"],
        ["doi"],
        ["title"],
        ["genre", "subspecialty"],
        ["journal", "topic"],
        ["abstract"],
    ]
    processor = DataProcessor(record_keys=record_keys, value_delimiter=None)
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == 2
    assert results[0]["authors.principle_investigator"] == "Dr. Smith"
    assert results[1]["authors.assistant"] == "John Roe"
    assert isinstance(results[0]["abstract"], list)
    assert results[1]["abstract"] == "Another abstract."


def test_filter_keys(mock_api_parsed_json_records):
    """
    Tests whether filtering and retaining a subset of records by key works as intended.
    The attributes, `keep_keys` and `ignore_keys` are used to determine whether a record should
    be excluded based on the name each of nested key in a path.
    """
    processor = DataProcessor(keep_keys=["principle_investigator"], regex=False)
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == 2

    processor = DataProcessor(keep_keys=["princip_invest"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0

    processor = DataProcessor(ignore_keys=["non-existent-key"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert len(results) == 2

    processor = DataProcessor(ignore_keys=["principle.*"])
    results = processor.process_page(mock_api_parsed_json_records)
    assert isinstance(results, list)
    assert len(results) == 0


def test_process_page_with_dict_keys(mock_api_parsed_json_records):
    """
    Verifies that using a dictionary of keys to dynamically rename the keys in the final dictionary works as intended.
    For example, instead of using the final path name, `authors.principle_investigator` as a key, `pi` is used instead.
    """
    record_keys: dict = {
        "pi": ["authors", "principle_investigator"],
        "assistant": ["authors", "assistant"],
        "doi": ["doi"],
        "title": ["title"],
        "subspecialty": ["genre", "subspecialty"],
        "topic": ["journal", "topic"],
        "abstract": ["abstract"],
    }
    processor = DataProcessor(record_keys=record_keys, value_delimiter=None)
    results = processor.process_page(mock_api_parsed_json_records)
    assert results[0]["pi"] == "Dr. Smith"
    assert results[1]["assistant"] == "John Roe"
    assert isinstance(results[0]["abstract"], list)
    assert results[1]["abstract"] == "Another abstract."

    assert 'authors.principle_investigator' not in results[0]
    assert 'authors.assistant' not in results[1]


@pytest.mark.parametrize("delimiter", (' | ', '%%', ';'))
def test_value_delimiter_joins_lists(delimiter, mock_api_parsed_json_records):
    """Validates the final delimiter used to join a list of records into a single string if specified."""
    record_keys: list[list] = [["abstract"]]
    processor = DataProcessor(record_keys=record_keys, value_delimiter=delimiter)
    results = processor.process_page(mock_api_parsed_json_records)
    assert results[0]["abstract"] == f"This is a sample abstract.{delimiter}keywords: 'sample', 'abstract'"
    assert results[1]["abstract"] == "Another abstract."


##### edge cases ######


def test_empty_record_keys_returns_empty_dict(mock_api_parsed_json_records):
    """
    Validates whether an attempt to extract records with an empty list of record keys
    will return an empty dictionary for each record as expected
    """
    processor = DataProcessor(record_keys=[])
    results = processor.process_page(mock_api_parsed_json_records)
    assert all(result == {} for result in results)


def test_empty_input_list_returns_empty_list():
    """Validates whether an attempt to process an empty page will, in return, return an empty page"""
    processor = DataProcessor(record_keys=[["title"]])
    results = processor.process_page([])
    assert results == []


def test_missing_path_returns_none():
    """
    Validates whether record keys that are not present will similarly still be displayed
    in the DataProcessor, but not contain data at the joined path
    """
    processor = DataProcessor(record_keys=[["not", "present"]])
    results = processor.process_page([{"foo": "bar"}])
    assert results[0]["not.present"] is None


def test_integer_index_in_path():
    """
    Tests whether including an numeric index within a path will be automatically be converted into a string as expected
    and enable retrieval of a record component at that path if available.
    """
    data: list = [{"a": [{"b": "val1"}, {"b": "val2"}]}]
    processor = DataProcessor(record_keys=[["a", 1, "b"]])
    results = processor.process_page(data)
    assert results[0]["a.1.b"] == "val2"


def test_non_string_values_are_handled():
    """
    Validates that non string values found within data paths can still be retrieved and converted into strings for
    delimited joins when the values are integers or mixed types.
    """
    data: list = [{"num": 123, "lst": [1, 2, 3]}]
    processor = DataProcessor(record_keys=[["num"], ["lst"]], value_delimiter="|")
    results = processor.process_page(data)
    assert results[0]["num"] == 123
    assert results[0]["lst"] == "1|2|3"


def test_none_values_are_handled():
    """Validates that `None` values are handled as expected, returning `None` for existing paths with NoneType values"""
    data: list = [{"foo": None}]
    processor = DataProcessor(record_keys=[["foo"]])
    results = processor.process_page(data)
    assert results[0]["foo"] is None


def test_empty_dict_in_record():
    """
    Validates that empty dictionary records within a list are populated with `None` types when possible,
    indicating that no data exists at the path.
    """
    data: list[dict] = [{}]
    processor = DataProcessor(record_keys=[["foo"]])
    results = processor.process_page(data)
    assert results[0]["foo"] is None


def test_path_with_integers():
    """Verifies that creating a path using integers with strings will parse correctly and retrieve existing paths"""
    data: list = [[{"bar": "baz"}], [{"bar": "qux"}]]
    processor = DataProcessor(record_keys=[[0, "bar"]])
    results = processor.process_page(data)
    assert results[0]["0.bar"] == "baz"
    assert results[1]["0.bar"] == "qux"


def test_process_page_with_regex():
    """
    Verifies that records containing keys in paths that match values from the `ignore_keys` attribute will be removed
    when the the page record data is processed.
    """
    data: list = [{"foo": "bar"}, {"baz": "qux"}]
    processor = DataProcessor(record_keys=[["foo"]])
    # Should filter out the first record if ignore_keys is ["foo"]
    results = processor.process_page(data, ignore_keys=["foo"])
    assert len(results) == 1
    assert "baz" not in results[0]


def test_record_filter_regex(mock_api_parsed_json_records):
    """Verifies that records filtered via regex will not be displayed in the full list of keys"""
    processor = DataProcessor(record_keys=[["title"]])
    # Should not filter out any records if ignore_keys is empty
    assert all(not processor.record_filter(rec) for rec in mock_api_parsed_json_records)
    # Should filter out records with "title" key
    assert all(processor.record_filter(rec, record_keys=["title"]) for rec in mock_api_parsed_json_records)


def test_invalid_record_keys_type_raises():
    """Validates whether specifying a list to a function that expects a list of strings will raise an error"""
    with pytest.raises(DataProcessingException):
        DataProcessor(record_keys="not a list or dict")  # type:ignore


def test_extract_key_returns_none_for_missing_key():
    """Verifies that paths that cannot be found in the record appear in the processed record with a value of None"""
    record: dict = {"foo": "bar"}
    assert DataProcessor.extract_key(record, "missing") is None


def test_extract_key_with_path():
    """
    Tests whether nested paths are extracted as intended with the `extract_key` method when given a key
    that is expected to contain data and the path where that key can be found
    """
    record: dict = {"a": {"b": {"c": [1, 2, 3]}}}
    assert DataProcessor.extract_key(record, "c", ["a", "b"]) == [1, 2, 3]


def test_prepare_record_keys_with_invalid_type():
    """Validates whether attempts to prepare a non-list or dictionary will raise an error as intended"""
    with pytest.raises(DataProcessingException):
        DataProcessor._prepare_record_keys("not a list or dict")  # type:ignore


def test_validate_inputs_with_invalid_types():
    """Validates whether specifying invalid inputs for DataProcessor attributes will raise an error as intended"""
    with pytest.raises(DataProcessingException):
        DataProcessor._validate_inputs("not a list or dict", "not a list or dict either", None, ";")  # type:ignore
    with pytest.raises(DataProcessingException):
        DataProcessor._validate_inputs([["a"]], "not a list", "not a list either", ";")  # type:ignore
    with pytest.raises(DataProcessingException):
        DataProcessor._validate_inputs([["a"]], None, None, 123)  # type:ignore


def test_collapse_fields_behavior():
    """
    Validates whether specifying a delimiter for collapsing fields will correctly join fields containing
    lists as terminal values.
    """
    processor = DataProcessor(record_keys=[["foo"]], value_delimiter=";")
    data = {"foo": ["a", "b"]}
    collapsed = processor.collapse_fields(data)
    assert collapsed["foo"] == "a;b"
    processor.value_delimiter = None
    collapsed = processor.collapse_fields(data)
    assert collapsed["foo"] == ["a", "b"]
