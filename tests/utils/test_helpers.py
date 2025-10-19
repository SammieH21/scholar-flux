# tests/test_utils.py
import logging
from requests import Response
from scholar_flux.utils.module_utils import set_public_api_module
from typing import Callable

import pytest

# Import the functions under test – adjust the module name as needed.
from scholar_flux.utils.helpers import (
    try_quote_numeric,
    quote_numeric,
    flatten,
    pattern_search,
    nested_key_exists,
    get_nested_dictionary_data,
    get_nested_data,
    generate_response_hash,
    compare_response_hashes,
    coerce_int,
    try_int,
    try_pop,
    try_dict,
    is_nested,
    unlist_1d,
    as_list_1d,
    path_search,
    try_call,
)


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


####################### Tests for coerce_int & try_int #########################


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
    """Verifies that an attempt to coerce both strings, NoneType values, and integers into an integer will result in the
    expected integer.

    This function will return an integer when the result is valid and
    None otherwise.
    """
    assert coerce_int(value) == expected


def test_try_int_success():
    """Verifies that an attempt to coerce both strings, NoneType values, and integers into an integer will result in the
    expected integer.

    This function will return the original value if conversion is not
    successful.
    """
    assert try_int("10") == 10
    assert try_int("xyz") == "xyz"


def test_try_int_none_value():
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

    Unsuccessful conversions are coerced into `None` while items such as
    lists are coerced into dictionaries with enumerated keys.
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

        pass

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
