# tests/test_utils.py
import importlib
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from requests import Response

from scholar_flux.api.validators import validate_bool_str

# Import the functions under test – adjust the module name as needed.
from scholar_flux.utils.helpers import (
    BeautifulSoup,
    as_list_1d,
    as_tuple,
    build_iso_date,
    coerce_bool,
    coerce_bytes,
    coerce_int,
    coerce_json_str,
    coerce_numeric,
    coerce_str,
    compare_response_hashes,
    convert_month_as_integer,
    extract_year,
    filter_record_key_prefixes,
    flatten,
    generate_response_hash,
    get_nested_data,
    get_nested_dictionary_data,
    get_values,
    infer_text_pattern_search,
    is_nested,
    is_nested_json,
    nested_key_exists,
    parse_iso_timestamp,
    path_search,
    pattern_search,
    quote_numeric,
    strip_html_tags,
    try_call,
    try_compile,
    try_dict,
    try_int,
    try_pop,
    try_quote_numeric,
    try_str,
    unlist_1d,
)
from scholar_flux.utils.module_utils import set_public_api_module

############################### Helper objects ################################


class DummyResponse(Response):
    """Helper class for subclassing a Response for further utility testing."""

    def __init__(self, url: str, headers, content: bytes, status_code: int = 200):
        """Initializes the DummyResponse."""
        self.url = url
        self.headers = headers
        self._content = content
        self.status_code = status_code


################### Tests for try_quote_numeric / quote_numeric ##############


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123", "'123'"),
        ("abc", None),
        (456, "'456'"),
        (12.3, None),
    ],
)
def test_try_quote_numeric(value, expected):
    """Tests whether attempts to quote only string values will return the expected value."""
    assert try_quote_numeric(value) == expected


def test_quote_numeric_success():
    """Tests whether attempts to quoting numeric string values will result in the expected, quoted string value."""
    assert quote_numeric("789") == "'789'"
    assert quote_numeric(0) == "'0'"


def test_quote_numeric_failure():
    """Validates whether attempting to use `quote_numeric` against a non-numeric value will raise a ValueError."""
    with pytest.raises(ValueError):
        quote_numeric("xyz")


############################## Tests for flatten ##############################


@pytest.mark.parametrize(
    ("data", "expected"),
    (
        (dict(a=1, b=2, c=3), False),
        (dict(a="a", b="b", c="c"), False),
        (None, False),
        ([], False),
        ({}, False),
        ([True, False, True], False),
        (3.14, False),
        ([{}, 2, 3], True),
        ({"a": [1, 2], "b": 2, "c": 3}, False),
        ({"a": [{"1": 2}], "b": 2, "c": 3}, True),
        ({"a": [["1", 2]], "b": 2, "c": 3}, True),
        (["a", [["1", 2]], "b", "c", 3], True),
    ),
)
def test_is_nested_json(data, expected):
    """Verifies that nested and unnested values can be identified correctly as intended."""
    assert is_nested_json(data) is expected


def test_flatten_single_dict_list():
    """Tests if calling `flatten` nested dictionary values will result in the expected dictionary value."""
    assert flatten([{"a": 1}]) == {"a": 1}
    assert flatten([{"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]
    assert flatten(None) is None
    assert flatten({}) == {}


################### Tests for pattern_search / path_search #################


@pytest.mark.parametrize(
    ("obj", "pattern", "regex", "expected"),
    [
        ({"foo": 1, "bar": 2}, "foo", True, ["foo"]),
        ({"foo": 1, "bar": 2}, "oo", False, ["foo"]),
        ({"foo": 1, "bar": 2}, "x", True, []),
    ],
)
def test_pattern_search(obj, pattern, regex, expected):
    """Tests whether combinations of patterns, regex flags, and objects will return the expected boolean value when
    checking for the presence of patterns in strings."""
    assert pattern_search(obj, pattern, regex) == expected


def test_path_search_alias():
    """Verifies whether the path_search function will retrieve the expected path from the current list of keys."""
    obj = {"foo": 1, "bar": 2}
    assert path_search(obj, "foo") == ["foo"]
    assert path_search(obj, "foo|bar") == ["foo", "bar"]
    assert path_search(obj, "f.*") == ["foo"]
    assert path_search(obj, "z") == []


############################## Tests for nested_key_exists ##############################


def test_filter_record_key_prefixes():
    """Verifies whether record keys are filtered as intended."""
    record: dict = {"a": 1, "b": 2, "bee": 3, "c": 4, 3: 5}
    assert filter_record_key_prefixes(record, prefix="a") == {"b": 2, "bee": 3, "c": 4, 3: 5}
    assert filter_record_key_prefixes(record, prefix="b") == {"a": 1, "c": 4, 3: 5}

    # Keep only elements beginning with a particular prefix
    assert filter_record_key_prefixes(record, prefix="a", invert=True) == {"a": 1}
    assert filter_record_key_prefixes(record, prefix="b", invert=True) == {"b": 2, "bee": 3}

    # Should remove all strings, keeping only non-strings
    assert filter_record_key_prefixes(record, prefix="") == {3: 5}

    # Should keep only strings
    assert filter_record_key_prefixes(record, prefix="", invert=True) == {"a": 1, "b": 2, "bee": 3, "c": 4}


def test_filter_record_key_prefix_edge_cases():
    """Verifies that `filter_record_key_prefixes` coerces prefixes into strings when not already a string."""
    record: dict = {"101": 1, "None": 0}
    assert filter_record_key_prefixes(record, prefix=1, invert=True) == {"101": 1}  # type: ignore
    assert filter_record_key_prefixes(record, prefix=None, invert=True) == {"None": 0}  # type: ignore


def test_filter_record_key_prefix_invalid_record_type():
    """Verifies that `filter_record_key_prefixes` raises a TypeError when the `record` type is incorrect."""
    invalid_record = "not a record"
    with pytest.raises(
        TypeError,
        match=f"Expected a dictionary record to filter key prefixes from, but received type {type(invalid_record)}",
    ):
        _ = filter_record_key_prefixes(invalid_record, prefix="a valid prefix")  # type: ignore


############################## Tests for nested_key_exists ##############################


def test_nested_key_exists_found():
    """Validates that nested records can be identified within dictionaries with nested components."""
    data = {"a": {"b": {"c": 1}}}
    assert nested_key_exists(data, "c") is True
    assert nested_key_exists(data, "c", regex=True) is True


def test_nested_key_exists_not_found():
    """Validates the absence of keys in the final result that do not match the inputted nested keys to search for."""
    data = {"a": {"b": {"c": 1}}}
    assert nested_key_exists(data, "x") is False


################ Tests for get_nested_dictionary_data / get_nested_data ##################


def test_get_nested_dictionary_data():
    """Verifies that nested elements within a dictionary are extracted given a path that contains those components."""
    d = {"a": {"b": {"c": 1}}}
    assert get_nested_dictionary_data(d, ["a", "b", "c"]) == 1
    assert get_nested_dictionary_data(d, ["a", "x"]) == {}


def test_get_nested_data_simple_and_nested():
    """Validates that an attempt to extract a simple nested path from a dictionary using integers and string values as
    keys will return the expected data point(s) at that inputted path."""
    json_obj = {"x": [1, 2, {"y": 3}]}
    assert get_nested_data(json_obj, ["x", 2, "y"]) == 3
    assert get_nested_data(json_obj, ["x", 10]) is None


############## Tests for generate_response_hash & compare_response_hashes #################


def test_generate_response_hash_and_compare():
    """Helper function for using the content of a response to create a hash for response comparison and equality
    tests."""
    resp1 = DummyResponse(
        "http://example.com",
        {"ETag": "123", "Last-Modified": "Mon, 01 Jan 2000"},
        b"hello",
    )
    resp2 = DummyResponse(
        "http://example.com",
        {"ETag": "123", "Last-Modified": "Mon, 01 Jan 2000"},
        b"hello",
    )
    resp3 = DummyResponse(
        "http://example.com",
        {"ETag": "999"},
        b"world",
    )

    h1 = generate_response_hash(resp1)
    h2 = generate_response_hash(resp2)
    h3 = generate_response_hash(resp3)

    assert h1 == h2
    assert h1 != h3
    assert compare_response_hashes(resp1, resp2) is True
    assert compare_response_hashes(resp1, resp3) is False


####################### Tests for coerce_int, coerce_numeric, try_int, coerce_str, and try_str #########################


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("42.123", 42.123),
        ("atl", None),
        (1, 1.0),
        (False, 0.0),  # edge case
        (3.14, 3.14),
    ],
)
def test_coerce_numeric(value, expected):
    """Tests if coercing numeric strings into floats returns the converted value when possible and None otherwise.

    This function will return an integer when the result is valid and None otherwise.

    """
    assert coerce_numeric(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("42", 42),
        ("abc", None),
        (None, None),
        (3.14, None),
    ],
)
def test_coerce_int(value, expected):
    """Tests if coercing integer strings into integers returns the converted value when possible and None otherwise.

    This function will return an integer when the result is valid and None otherwise.

    """
    assert coerce_int(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("42", "42"),
        ("abc", "abc"),
        (None, None),
        (3.14, "3.14"),
        (b"abc", "abc"),
        (["abc", "tev"], "['abc', 'tev']"),
        (sum, "<built-in function sum>"),
    ],
)
def test_try_str(value, expected):
    """Tests the behavior of `try_str`, which converts values into strings and otherwise returns the original value.

    This function will return an integer when the result is valid and the original value otherwise.

    """
    assert try_str(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("42", "42"),
        ("abc", "abc"),
        (None, None),
        (3.14, "3.14"),
        (["abc", "tev"], "['abc', 'tev']"),
        (b"abc", "abc"),
        (sum, "<built-in function sum>"),
    ],
)
def test_coerce_str(value, expected):
    """Tests if coercing types into strings returns a string when coercible and None otherwise."""
    assert coerce_str(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("24", b"24"),
        ("cba", b"cba"),
        (None, None),
        (3.14, None),
        (["abc", "tev"], None),
        (b"abc", b"abc"),
    ],
)
def test_coerce_bytes(value, expected):
    """Tests if `coerce_bytes` returns a bytes object when coercible and None otherwise."""
    assert coerce_bytes(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("42", "42"),
        ("abc", "abc"),
        (None, None),
        (3.14, "3.14"),
        (["abc", "tev"], "['abc', 'tev']"),
        (b"abc", "abc"),
        (sum, "<built-in function sum>"),
    ],
)
def test_coerce_bytes_string_round_trip(value, expected):
    """Verifies that coercion from string to bytes and back to string returns consistent results roundtrip."""
    as_string = coerce_str(value)
    as_bytes = coerce_bytes(as_string)
    assert as_string == expected and (isinstance(as_bytes, bytes) ^ (expected is None and as_bytes is None))
    assert coerce_str(as_bytes) == expected


def test_coerce_bytes_with_bad_encoding():
    """Verifies that coercion from string to bytes raises when a bad encoding is passed."""
    assert coerce_bytes("a valid string", encoding="An invalid encoding") is None


def test_try_int_success():
    """Verifies that an attempt to coerce both strings, NoneType values, and integers into an integer will result in the
    expected integer.

    This function will return the original value if conversion is not successful.

    """
    assert try_int("10") == 10
    assert try_int("xyz") == "xyz"


def test_try_int_none_value():
    """Verifies that an attempt to convert a NoneType variable into an integer, in-turn, returns None."""
    assert try_int(None) is None


def test_try_str_none_value():
    """Verifies that an attempt to convert a NoneType variable into an integer, in-turn, returns None."""
    assert try_int(None) is None


############################## Tests for try_pop ################################


def test_try_pop_existing_and_missing():
    """Validates whether the `try_pop` function successfully removes an object that exists within a set and returns the
    default when the object does not exist in the set."""
    s = {1, 2, 3}
    assert try_pop(s, 2) == 2
    assert 2 not in s
    assert try_pop(s, 5, default="missing") == "missing"  # type:ignore
    assert try_pop(s, 5) is None


############################## Tests for try_dict ################################


def test_try_dict_cases():
    """Validates the functionality of `try_dict` to verify attempted dict conversions against expected values.

    Unsuccessful conversions are coerced into `None` while items such as lists are coerced into dictionaries with
    enumerated keys.

    """
    assert try_dict({"a": 1}) == {"a": 1}
    assert try_dict([{"a": 1}, {"b": 2}]) == {0: {"a": 1}, 1: {"b": 2}}
    assert try_dict("invalid") is None  # type:ignore
    test_list = [1, 2, 3]
    test_tuple = tuple(test_list)

    assert try_dict(test_list) == try_dict(test_tuple) == {0: 1, 1: 2, 2: 3}  # type:ignore


############################## Tests for is_nested ################################


def test_is_nested():
    """Verifies that mappings, sequences, and sets are correctly identified as nested while strings/ints are not."""
    assert is_nested({"a": 1}) is True
    assert is_nested({"a", 1}) is True
    assert is_nested([1, 2]) is True
    assert is_nested((1, 2)) is True
    assert is_nested("string") is False
    assert is_nested(42) is False
    assert is_nested(DummyResponse) is False


############################## Tests for unlist_1d ################################


def test_unlist_1d():
    """Verifies whether attempting to unlist singular elements within a list will result in the expected value."""
    assert unlist_1d([42]) == 42
    assert unlist_1d((42,)) == 42
    assert unlist_1d([{1, 2}]) == {1, 2}
    assert unlist_1d(
        [
            (
                1,
                2,
            )
        ]
    ) == (
        1,
        2,
    )
    assert unlist_1d([[1, 2]]) == [1, 2]
    assert unlist_1d([{1: "a", 2: "b"}]) == {1: "a", 2: "b"}
    assert unlist_1d(42) == 42  # type: ignore


############################## Tests for as_list_1d ###############################


def test_as_list_1d():
    """Verifies that attempts to nest various data types in a list (if not already a list) will result in the expected
    value."""
    assert as_list_1d(None) == []
    assert as_list_1d([1, 2]) == [1, 2]
    assert as_list_1d((5,)) == [(5,)]
    assert as_list_1d({5}) == [{5}]
    assert as_list_1d({"a": 5}) == [{"a": 5}]
    assert as_list_1d(5) == [5]
    assert as_list_1d("x") == ["x"]


############################## Tests for try_call ###############################


def dummy_func(a, *, b=0):
    """A simple test function used to determine whether the `try_call` function works as intended."""
    return a + b


def error_func():
    """Basic function for directly raising a runtime error to verify the behavior `try_call` on known exceptions."""
    raise RuntimeError("boom")


def test_try_call_success():
    """Validates whether `try_call` successfully returns the expected result when used as intended."""
    assert try_call(dummy_func, args=(2,), kwargs={"b": 3}) == 5


def test_try_call_no_suppress():
    """Validates whether the expected error is raised when not specifying `suppress=(RuntimeError,)`"""
    with pytest.raises(RuntimeError):
        try_call(error_func)


def test_try_call_with_suppress(caplog):
    """Validates whether, on catching an error, log levels and fallbacks work as intended."""
    logger = logging.getLogger("test_logger")
    result = try_call(error_func, suppress=(RuntimeError,), logger=logger, log_level=logging.ERROR, default="fallback")
    assert result == "fallback"
    assert (
        "An error occurred in the call to the function argument, 'error_func', args=(), kwargs={}: boom" in caplog.text
    )


def test_try_call_non_callable(caplog):
    """Tests the `try_call` function to determine whether non-function/callable inputs result in the expected side-
    effect.

    If the resulting exception is not suppressed, `try_call` should raise a TypeError. Otherwise, `suppress=(TypeError,)`
    should successfully catch the error and default to a value specified by the user and None if not directly specified.

    This test also verifies that the exception, if caught, will also display in the logger if configured and specified.

    """
    default = "not callable"
    logger = logging.getLogger("test_logger")
    with pytest.raises(TypeError) as excinfo:
        _ = try_call(123, default=default)  # type:ignore
    value = try_call(123, default=default, suppress=(TypeError,), logger=logger)  # type:ignore
    assert value == default
    assert str(excinfo.value) in caplog.text


@pytest.fixture
def new_int():
    """Helper int for testing whether ints (don't have a __module__ attr) are skipped when setting public api
    modules."""
    return 1


@pytest.fixture()
def new_set() -> set:
    """Helper set for testing whether sets (don't have a __module__ attr) are skipped when setting public api
    modules."""
    return {1, 2, 3}


@pytest.fixture()
def new_tuple() -> tuple:
    """Helper tuple for verifying whether new classes are successfully renamed."""
    return (4, 5, 6)


@pytest.fixture()
def new_fn() -> Callable:
    """Uses a builtin function to test whether `set_public_api_module` successfully renames function modules."""
    return lambda x: x


@pytest.fixture()
def new_class() -> object:
    """Creates a helper class to test whether `set_public_api_module` successfully renames class modules."""

    class AClass:
        """A dummy class for testing."""

    return AClass


def test_set_public_api_module(new_int, new_set, new_tuple, new_fn, new_class):
    """Tests the set_public_api_module to verify that the module names of only functions and classes are modified."""

    __all__ = [
        "try_quote_numeric",
        "quote_numeric",
        "flatten",
        "new_int",
        "new_tuple",
        "new_set",
        "new_fn",
        "new_class",
    ]

    set_public_api_module(__name__, __all__, globals())

    assert all(
        fn.__module__ == __name__ if hasattr(fn, "__module__") else not callable(fn)
        for fn in [try_quote_numeric, quote_numeric, flatten, new_int, new_tuple, new_set, new_fn, new_class]
    )


############################## Tests for as_tuple ################################


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ((1, 2, 3), (1, 2, 3)),  # tuple returns unchanged
        ([1, 2, 3], (1, 2, 3)),  # list converted to tuple
        ({1, 2, 3}, (1, 2, 3)),  # set converted to tuple (order may vary)
        (None, ()),  # None returns empty tuple
        (42, (42,)),  # scalar wrapped in tuple
        ("string", ("string",)),  # string wrapped in tuple
        ({"a": 1}, ({"a": 1},)),  # dict wrapped in tuple
    ],
)
def test_as_tuple(value, expected):
    """Validates that as_tuple correctly converts or wraps values into tuples."""
    result = as_tuple(value)
    if isinstance(value, set):
        # Sets don't have guaranteed order, so compare as sets
        assert set(result) == set(expected)
    else:
        assert result == expected


def test_as_tuple_preserves_tuple():
    """Verifies that an existing tuple is returned unchanged."""
    original = (1, 2, 3)
    assert as_tuple(original) is original


############################## Tests for nested_key_exists in lists ################################


def test_nested_key_exists_in_list():
    """Validates that nested_key_exists finds keys within dictionaries nested in lists."""
    data = [{"a": 1}, {"b": {"c": 2}}]
    assert nested_key_exists(data, "c") is True
    assert nested_key_exists(data, "a") is True
    assert nested_key_exists(data, "x") is False


def test_nested_key_exists_deeply_nested_list():
    """Validates that nested_key_exists works with deeply nested list structures."""
    data = {"items": [{"nested": [{"deep_key": "value"}]}]}
    assert nested_key_exists(data, "deep_key") is True


############################## Tests for coerce_str exception handling ################################


def test_coerce_str_unicode_decode_error():
    """Validates that coerce_str returns None when bytes cannot be decoded with the specified encoding."""
    # Invalid UTF-8 byte sequence
    invalid_bytes = b"\xff\xfe"
    assert coerce_str(invalid_bytes, encoding="ascii") is None


def test_coerce_str_invalid_encoding():
    """Validates that coerce_str handles invalid encoding gracefully."""
    # Bytes that are valid UTF-8 but not valid ASCII
    utf8_bytes = b"\xc3\xa9"  # é in UTF-8
    assert coerce_str(utf8_bytes, encoding="ascii") is None


############################## Tests for get_values ################################


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("string", []),  # strings are not nested
        (42, []),  # integers are not nested
        (3.14, []),  # floats are not nested
        (None, []),  # None is not nested
    ],
)
def test_get_values_non_nested(value, expected):
    """Validates that get_values returns an empty list for non-nested types."""
    assert list(get_values(value)) == expected


def test_get_values_dict():
    """Validates that get_values returns dictionary values."""
    data = {"a": 1, "b": 2}
    assert list(get_values(data)) == [1, 2]


def test_get_values_list():
    """Validates that get_values returns the list itself for iteration."""
    data = [1, 2, 3]
    assert list(get_values(data)) == [1, 2, 3]


############################## Tests for parse_iso_timestamp ################################


@pytest.mark.parametrize(
    "value",
    [
        123,  # integer
        12.34,  # float
        None,  # NoneType
        ["2024-01-01"],  # list
        {"date": "2024-01-01"},  # dict
    ],
)
def test_parse_iso_timestamp_non_string(value):
    """Validates that parse_iso_timestamp returns None for non-string inputs."""
    assert parse_iso_timestamp(value) is None


def test_parse_iso_timestamp_valid():
    """Validates that parse_iso_timestamp correctly parses valid ISO timestamps."""
    result = parse_iso_timestamp("2024-12-18T10:30:00Z")
    assert result is not None
    assert result.year == 2024
    assert result.month == 12
    assert result.day == 18


def test_parse_iso_timestamp_invalid_format():
    """Validates that parse_iso_timestamp returns None for invalid date formats."""
    assert parse_iso_timestamp("not-a-date") is None
    assert parse_iso_timestamp("") is None


############################## Tests for convert_month_as_integer ################################


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),  # None input
        ("", None),  # empty string
        ("1", "01"),  # single digit
        ("12", "12"),  # double digit
        ("Jan", "01"),  # abbreviated month name
        ("January", "01"),  # full month name
        ("dec", "12"),  # lowercase
        ("DEC", "12"),  # uppercase
        ("invalid", None),  # invalid month name
        ("13", None),  # out of range number
        ("0", None),  # zero
    ],
)
def test_convert_month_as_integer(value, expected):
    """Validates that convert_month_as_integer correctly converts month names and numbers."""
    assert convert_month_as_integer(value) == expected


############################## Tests for coerce_json_str ################################


def test_string_typed_json_coercion(mock_academic_json):
    """Verifies that strings are returned only when they can be successfully loaded as a JSON dict/list."""
    serialized_dict = coerce_json_str(mock_academic_json)
    assert isinstance(serialized_dict, str)
    # string returned when json.loads returns a dict or str
    assert coerce_json_str(serialized_dict) == serialized_dict
    serialized_list = f"[{serialized_dict}]"
    assert serialized_list == coerce_json_str([mock_academic_json])

    # re-serialization of strings that are JSON loadable as dicts/lists is returns the same input
    assert serialized_list == coerce_json_str(coerce_json_str([mock_academic_json]))

    # auto converts bytes (assuming utf-8)
    assert coerce_json_str(serialized_dict.encode("utf-8")) == serialized_dict


@pytest.mark.parametrize(
    "value",
    (
        # can't encode bytes
        {b"a non-dumpable key": "a valid json value"},
        [b"a non-dumpable key", "a valid json value"],
        # only excepts sequences, mappings, and strings that can be loaded into a list/dicts
        "a non-dict/list",
        False,
        0,
        {1, 2, 3},
        (1, 3, 5, b"7"),
    ),
)
def test_json_string_coercion_failure(value: object):
    """Verifies that errors are caught when an error occurs from calling `json.dumps()`."""
    assert coerce_json_str(value) is None


############################## Tests for build_iso_date ################################


@pytest.mark.parametrize(
    ("year", "month", "day", "expected"),
    [
        ("2025", "12", "19", "2025-12-19"),  # full date
        ("2025", "Dec", "19", "2025-12-19"),  # month name
        ("2025", "12", "", "2025-12"),  # year-month only
        ("2025", "Dec", "", "2025-12"),  # year-month with name
        ("2025", "", "", "2025"),  # year only
        ("2025", None, None, "2025"),  # year only with None
        ("", "12", "19", None),  # empty year
        (None, "12", "19", None),  # None year
        ("invalid", "12", "19", None),  # non-numeric year
        ("2025", "1", "5", "2025-01-05"),  # single digit month and day
    ],
)
def test_build_iso_date(year, month, day, expected):
    """Validates that build_iso_date correctly builds ISO date strings with graduated precision."""
    assert build_iso_date(year, month, day) == expected


def test_build_iso_date_invalid_day():
    """Validates that build_iso_date handles invalid day values."""
    # Day out of valid range should be ignored
    assert build_iso_date("2025", "12", "32") == "2025-12"
    assert build_iso_date("2025", "12", "0") == "2025-12"


# #################### Tests for extract_year ####################


def test_extract_year_custom_format():
    """Test year extraction with custom date format."""
    assert extract_year("03/15/2024", format="%m/%d/%Y") == 2024


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-03-01", 2026),
        ("2024-12-18T10:30:00Z", 2024),
        (date(2026, 3, 1), 2026),
        (datetime(2024, 12, 1, 12, 0, 0, tzinfo=timezone.utc), 2024),
        ("2023", 2023),
        ("03/15/2024", 2024),
        ("Published in 2022 edition", 2022),
        ("not a date", None),
        ("", None),
        (None, None),
        ("no year here", None),
    ],
)
def test_extract_year_parametrized(value, expected):
    """Parametrized test for extract_year."""
    assert extract_year(value) == expected


# #################### Tests for validate_bool_str ####################


def test_validate_bool_str_invalid_type():
    """Test validation with non-string input raises ValueError."""
    with pytest.raises(ValueError, match="Expected str"):
        validate_bool_str(123)  # type: ignore


def test_validate_bool_str_custom_true_values():
    """Test validation with custom true values."""
    assert validate_bool_str("on", true_values=("on", "enabled")) is True
    assert validate_bool_str("off", true_values=("on", "enabled")) is False


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("false", False),
        ("FALSE", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("no", False),
        ("random", False),
        ("", False),
        (None, None),
    ],
)
def test_validate_bool_str_parametrized(value, expected):
    """Verifies that `validate_bool_str` operates as intended for all possible intended validation cases."""
    assert validate_bool_str(value) == expected


# #################### Tests for coerce_bool ####################


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        ("true", True),
        ("TRUE", True),
        ("T", True),
        ("yes", True),
        (1, True),
        (False, False),
        ("false", False),
        ("FALSE", False),
        ("F", False),
        ("0", False),
        ("no", False),
        ("random", None),
        ("None", None),
        ({}, None),
        ((), None),
        ("", None),
        (None, None),
    ],
)
def test_coerce_bool_parametrized(value, expected):
    """Verifies that `coerce_bool` operates as intended for common values and edge cases."""
    assert coerce_bool(value) == expected


def test_coerce_bool_without_true_false_values():
    """Verifies that only returns exact `True` and `False` boolean values when true/false value tuples are empty."""
    assert coerce_bool(True, true_values=(), false_values=()) is True
    assert coerce_bool(False, true_values=(), false_values=()) is False
    assert coerce_bool("True", true_values=(), false_values=()) is None
    assert coerce_bool("False", true_values=(), false_values=()) is None


def test_coerce_bool_with_custom_true_false_values():
    """Verifies that custom values can be mapped to True and False without case-sensitivity."""
    is_blue = ("BLUE", "cyan", "ocean", "sky")
    not_blue = ("Green", "wood", "GRASS", "Red")

    assert all(coerce_bool(val.upper(), true_values=is_blue, false_values=not_blue) is True for val in is_blue)
    assert all(coerce_bool(val.lower(), true_values=is_blue, false_values=not_blue) is False for val in not_blue)

    assert coerce_bool("who", true_values=is_blue, false_values=not_blue) is None
    assert coerce_bool("NONE", true_values=is_blue, false_values=not_blue) is None


##################### Tests for get_nested_data edge cases ####################


@pytest.fixture
def nested_records():
    """Fixture of sample nested record structures for verifying nested JSON traversal edge_cases."""
    return {
        "simple_nested": {"a": {"b": {"c": "value"}}},
        "list_nested": {"data": [{"id": 1}, {"id": 2}]},
        "mixed_nested": {"items": [{"name": "item1", "meta": {"count": 5}}]},
        "single_element_list": {"data": [{"value": "single"}]},
        "empty": {},
    }


def test_get_nested_data_simple_path(nested_records):
    """Tests nested data extraction with simple path."""
    result = get_nested_data(nested_records["simple_nested"], ["a", "b", "c"])
    assert result == "value"


def test_get_nested_data_list_index(nested_records):
    """Tests nested data extraction when using a numeric index."""
    result = get_nested_data(nested_records["list_nested"], ["data", 0, "id"])
    assert result == 1


def test_get_nested_data_missing_path(nested_records):
    """Tests nested data extraction with a missing path."""
    result = get_nested_data(nested_records["simple_nested"], ["x", "y", "z"])
    assert result is None


def test_get_nested_data_flatten_single_dict(nested_records):
    """Tests that intermediate, single element lists are traversed when using `flatten_nested_dictionaries=False`."""
    result = get_nested_data(nested_records["single_element_list"], ["data", "value"], flatten_nested_dictionaries=True)
    assert result == "single"


def test_get_nested_data_no_flatten(nested_records):
    """Tests that keys are traversed without additional flattening when using `flatten_nested_dictionaries=False`."""
    result = get_nested_data(nested_records["single_element_list"], ["data"], flatten_nested_dictionaries=False)
    assert result == [{"value": "single"}]


########################### Tests for Pattern Matching Inference ########################


@pytest.mark.parametrize(
    "value,expected,kwargs",
    [
        # Basic strings that can be compiled into patterns
        ("apple", re.compile("apple"), {}),
        ("APPLE", re.compile("APPLE"), {}),
        ("APPLE", re.compile("my APPLE"), {"prefix": "my "}),
        ("MY APPLE", re.compile("MY APPLE"), {"prefix": "MY "}),
        ("B|C|D", re.compile("a B|a C|a D"), {"prefix": "a "}),
        (r"B|C\|D", re.compile(r"a B.|a C\|D."), {"prefix": "a ", "suffix": "."}),
        (r"B|C\\|D", re.compile(r"a B.|a C\\.|a D."), {"prefix": "a ", "suffix": "."}),
        # Non-strings
        (None, None, {}),
        (12, re.compile("12"), {}),
        (False, re.compile("False"), {}),
        ({"hello": "world"}, re.compile(str({"hello": "world"})), {}),
        # Patterns that shouldn't compile
        ("Banana(?<*)", None, {}),  # Can't use a lookbehind with unknown string lengths
        ("(Banana", None, {}),  # The closing parentheses is missing
        # Edge cases that compile (regex patterns are eagerly returned)
        ("Banana)", re.compile(r"Banana\)"), {"escape": True}),
        (re.compile("[a-z]"), re.compile("[a-z]"), {"flags": "not a flag"}),
    ],
)
def test_basic_compiling(value, expected, kwargs):
    """Tests that the `try_compile` method correctly compiles strings when possible and returns None otherwise."""
    assert try_compile(value, **kwargs) == expected


def test_try_compile_error_logging(caplog):
    """Tests if `try_compile` logs error messages with `verbose=True` given an invalid string."""
    no_pattern = try_compile("this is an invalid pattern :)", verbose=True)
    assert no_pattern is None
    pattern = try_compile("error.*unbalanced parenthesis")
    assert pattern is not None and re.search(pattern, caplog.text)


def test_try_compile_caching():
    """Verifies that the originally cached pattern is returned when compiling the same string."""
    pat1 = try_compile("abc")
    pat2 = try_compile("abc")
    assert pat1 is pat2 is re.compile("abc")  # Should be the same object due to regular expression-based caching.


def test_basic_inferred_text_pattern_matching():
    """Verifies order-based pattern matching logic against a dictionary of regex pattern-match mappings.

    The patterns should be checked in order of definition/insertion for python versions 3.7+:

    """
    patterns = {"^a.*": "a", ".*b.*": "b", ".*c.*": "c"}

    # basic pattern matching with regex
    assert infer_text_pattern_search("abe", patterns, default=None) == "a"
    assert infer_text_pattern_search("ebc", patterns, default=None) == "b"
    assert infer_text_pattern_search("eec", patterns, default=None) == "c"
    assert infer_text_pattern_search("ddd", patterns) is None
    assert infer_text_pattern_search("ddd", patterns, default="") == ""
    # Case sensitive by default
    assert infer_text_pattern_search("Abc", patterns, default=None) == "b"

    # if the value is not a dict or is an empty string, the default value should be returned
    assert infer_text_pattern_search({"a"}, patterns, default="") == ""  # type: ignore
    assert infer_text_pattern_search("", patterns, default="") == ""  # type: ignore


def test_nonregex_text_pattern_matching():
    """Verifies order-based non-regex pattern matching logic against a dictionary of fixed pattern-match mappings."""
    patterns = {"Yes": True, "No": False, "[N/A]": None}

    for pattern, expected in patterns.items():
        assert infer_text_pattern_search(f"Answer: {pattern}", patterns, default="", regex=False) is expected

    assert infer_text_pattern_search("Answer: Who knows?", patterns, default="", regex=False) == ""
    assert infer_text_pattern_search("Answer: YES", patterns, default=None, regex=False, flags=re.IGNORECASE) is True
    assert infer_text_pattern_search("Answer: YES", patterns, default=None, regex=False) is None

    # Unexpected patterns should be directly converted into strings. The following is valid, although not recommended:
    assert infer_text_pattern_search("Answer: None", patterns | {None: False}, regex=False) is False  # type: ignore


############################ Tests for BeautifulSoup text parsing #######################


def test_strip_html_tags_basic_div():
    """Verifies the behavior of the `strip_html_tags` when installed and available against a basic html string."""
    if BeautifulSoup is None:
        pytest.skip("BeautifulSoup is not installed, skipping check for tag extraction...")
    paragraph_one = "This is a paragraph."
    paragraph_two = "This is another paragraph"
    text_with_html = f"<div><p>{paragraph_one}</p><br><p>{paragraph_two}</p></div>"
    stripped_text = f"{paragraph_one}{paragraph_two}"
    assert strip_html_tags(text_with_html) == stripped_text
    assert stripped_text == strip_html_tags(stripped_text)  # should return the exact string


def test_strip_html_tags_nonstring():
    """Verifies that `strip_html_tags` returns the exact input when a non-string is received (e.g., list, None, int)."""
    if BeautifulSoup is None:
        pytest.skip("BeautifulSoup is not installed, skipping check for non-string behavior...")

    assert strip_html_tags(1) == 1  # type: ignore
    assert strip_html_tags(None) is None  # type: ignore
    assert strip_html_tags([1, 2, 3, 4]) == [1, 2, 3, 4]  # type: ignore


def test_strip_html_bs4_missing(caplog):
    """Verifies the behavior of the `strip_html_tags` function when `beautifulsoup4` is missing.

    Note:
        The direct import of the helpers module is necessary for patching, testing tag removal behavior without `bs4`,
        and reloading the module after testing for cleanup.

    """
    import scholar_flux.utils.helpers

    try:
        with patch.dict("sys.modules", {"bs4": None}):
            importlib.reload(scholar_flux.utils.helpers)
            import scholar_flux.utils.helpers

            assert scholar_flux.utils.helpers.BeautifulSoup is None
            text_with_html = "<p>This is a paragraph with html tags</p>"
            # Shouldn't strip since bs4 isn't available
            assert scholar_flux.utils.helpers.strip_html_tags(text_with_html) == text_with_html
            assert "`beautifulsoup4` is not installed. Skipping html tag removal..." in caplog.text
    finally:
        importlib.reload(scholar_flux.utils.helpers)
