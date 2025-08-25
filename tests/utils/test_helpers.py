# tests/test_utils.py
import hashlib
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pytest
import requests

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

# --------------------------------------------------------------------------- #
# Helper objects
# --------------------------------------------------------------------------- #
@dataclass
class DummyResponse:
    url: str
    headers: Dict[str, str]
    content: bytes

    def __init__(self, url: str, headers: Dict[str, str], content: bytes):
        self.url = url
        self.headers = headers
        self.content = content

# --------------------------------------------------------------------------- #
# Tests for try_quote_numeric / quote_numeric
# --------------------------------------------------------------------------- #
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
    assert try_quote_numeric(value) == expected


def test_quote_numeric_success():
    assert quote_numeric("789") == "'789'"
    assert quote_numeric(0) == "'0'"


def test_quote_numeric_failure():
    with pytest.raises(ValueError):
        quote_numeric("xyz")


# --------------------------------------------------------------------------- #
# Tests for flatten
# --------------------------------------------------------------------------- #
def test_flatten_single_dict_list():
    assert flatten([{"a": 1}]) == {"a": 1}
    assert flatten([{"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]
    assert flatten(None) is None
    assert flatten({}) == {}


# --------------------------------------------------------------------------- #
# Tests for pattern_search / path_search
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("obj", "pattern", "regex", "expected"),
    [
        ({"foo": 1, "bar": 2}, "foo", True, ["foo"]),
        ({"foo": 1, "bar": 2}, "oo", False, ["foo"]),
        ({"foo": 1, "bar": 2}, "x", True, []),
    ],
)
def test_pattern_search(obj, pattern, regex, expected):
    assert pattern_search(obj, pattern, regex) == expected


def test_path_search_alias():
    obj = {"foo": 1, "bar": 2}
    assert path_search(obj, "foo") == ["foo"]


# --------------------------------------------------------------------------- #
# Tests for nested_key_exists
# --------------------------------------------------------------------------- #
def test_nested_key_exists_found():
    data = {"a": {"b": {"c": 1}}}
    assert nested_key_exists(data, "c") is True
    assert nested_key_exists(data, "c", regex=True) is True


def test_nested_key_exists_not_found():
    data = {"a": {"b": {"c": 1}}}
    assert nested_key_exists(data, "x") is False


# --------------------------------------------------------------------------- #
# Tests for get_nested_dictionary_data / get_nested_data
# --------------------------------------------------------------------------- #
def test_get_nested_dictionary_data():
    d = {"a": {"b": {"c": 1}}}
    assert get_nested_dictionary_data(d, ["a", "b", "c"]) == 1
    assert get_nested_dictionary_data(d, ["a", "x"]) == {}


def test_get_nested_data_simple_and_nested():
    json_obj = {"x": [1, 2, {"y": 3}]}
    assert get_nested_data(json_obj, ["x", 2, "y"]) == 3
    assert get_nested_data(json_obj, ["x", 10]) is None


# --------------------------------------------------------------------------- #
# Tests for generate_response_hash & compare_response_hashes
# --------------------------------------------------------------------------- #
def test_generate_response_hash_and_compare():
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


# --------------------------------------------------------------------------- #
# Tests for coerce_int & try_int
# --------------------------------------------------------------------------- #
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
    assert coerce_int(value) == expected


def test_try_int_success():
    assert try_int("10") == 10
    assert try_int("xyz") == "xyz"


def test_try_int_none_value():
    assert try_int(None) is None


# --------------------------------------------------------------------------- #
# Tests for try_pop
# --------------------------------------------------------------------------- #
def test_try_pop_existing_and_missing():
    s = {1, 2, 3}
    assert try_pop(s, 2) == 2
    assert 2 not in s
    assert try_pop(s, 5, default="missing") == "missing" # type:ignore
    assert try_pop(s, 5) is None


# --------------------------------------------------------------------------- #
# Tests for try_dict
# --------------------------------------------------------------------------- #
def test_try_dict_cases():
    assert try_dict({"a": 1}) == {"a": 1}
    assert try_dict([{"a": 1}, {"b": 2}]) == {0: {"a": 1}, 1: {"b": 2}}
    assert try_dict("invalid") is None #type:ignore

    assert try_dict([1, 2, 3]) == {0: 1, 1: 2, 2: 3} # type:ignore


# --------------------------------------------------------------------------- #
# Tests for is_nested
# --------------------------------------------------------------------------- #
def test_is_nested():
    assert is_nested({"a": 1}) is True
    assert is_nested([1, 2]) is True
    assert is_nested("string") is False
    assert is_nested(42) is False


# --------------------------------------------------------------------------- #
# Tests for unlist_1d
# --------------------------------------------------------------------------- #
def test_unlist_1d():
    assert unlist_1d([42]) == 42
    assert unlist_1d((42,)) == 42
    assert unlist_1d([1, 2]) == [1, 2]
    assert unlist_1d((1, 2)) == (1, 2)
    assert unlist_1d(42) == 42


# --------------------------------------------------------------------------- #
# Tests for as_list_1d
# --------------------------------------------------------------------------- #
def test_as_list_1d():
    assert as_list_1d(None) == []
    assert as_list_1d([1, 2]) == [1, 2]
    assert as_list_1d(5) == [5]
    assert as_list_1d("x") == ["x"]


# --------------------------------------------------------------------------- #
# Tests for try_call
# --------------------------------------------------------------------------- #
def dummy_func(a, b=0):
    return a + b


def error_func():
    raise RuntimeError("boom")


def test_try_call_success():
    assert try_call(dummy_func, args=(2,), kwargs={"b": 3}) == 5


def test_try_call_no_suppress():
    with pytest.raises(RuntimeError):
        try_call(error_func)


def test_try_call_with_suppress():
    logger = logging.getLogger("test_logger")
    result = try_call(error_func, suppress=(RuntimeError,), logger=logger, log_level=logging.ERROR, default="fallback")
    assert result == "fallback"


def test_try_call_non_callable():
    with pytest.raises(TypeError):
        result = try_call(123, default="not callable") #type:ignore
