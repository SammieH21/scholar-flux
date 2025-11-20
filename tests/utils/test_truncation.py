import pytest
from scholar_flux.utils.repr_utils import truncate


def test_truncate_none():
    """Test truncating None returns 'None'."""
    assert truncate(None) == "None"
    assert truncate(None, max_length=10) == "None"


def test_truncate_short_string():
    """Test that short strings are not truncated."""
    short_str = "Hello"
    assert truncate(short_str, max_length=40) == "Hello"
    assert truncate(short_str, max_length=10) == "Hello"


def test_truncate_long_string():
    """Test that long strings are truncated with suffix."""
    long_str = "A very long string that needs truncation"
    result = truncate(long_str, max_length=21)
    assert len(result) == 21
    assert result == "A very long string..."
    assert result.endswith("...")


def test_truncate_string_custom_suffix():
    """Test truncating strings with custom suffix."""
    long_str = "A very long string"
    result = truncate(long_str, max_length=15, suffix=">>")
    assert len(result) == 15
    assert result.endswith(">>")


def test_truncate_empty_string():
    """Test truncating empty string."""
    assert truncate("", max_length=40) == ""


def test_truncate_short_dict():
    """Test that short dicts are not truncated."""
    short_dict = {"a": 1, "b": 2}
    result = truncate(short_dict, max_length=50)
    assert result == str(short_dict)


def test_truncate_long_dict_with_count():
    """Test that long dicts are truncated with count."""
    long_dict = {f"key{i}": f"value{i}" for i in range(10)}
    result = truncate(long_dict, max_length=30, show_count=True)

    assert result.endswith("} (10 items)")
    assert "..." in result
    assert result.startswith("{")


def test_truncate_long_dict_without_count():
    """Test that long dicts are truncated without count when show_count=False."""
    long_dict = {f"key{i}": f"value{i}" for i in range(10)}
    result = truncate(long_dict, max_length=30, show_count=False)

    assert " items)" not in result
    assert "..." in result
    assert result.endswith("}")


def test_truncate_single_item_dict():
    """Test that single-item dict shows '(1 item)' not '(1 items)'."""
    single_dict = {"key": "a very long value that will cause truncation to occur"}
    result = truncate(single_dict, max_length=30, show_count=True)

    assert "(1 item)" in result


def test_truncate_empty_dict():
    """Test truncating empty dict."""
    assert truncate({}, max_length=40) == "{}"


def test_truncate_short_list():
    """Test that short lists are not truncated."""
    short_list = [1, 2, 3]
    result = truncate(short_list, max_length=50)
    assert result == str(short_list)


def test_truncate_long_list_with_count():
    """Test that long lists are truncated with count."""
    long_list = [{"id": f"item_{i}", "value": i} for i in range(25)]
    result = truncate(long_list, max_length=40, show_count=True)

    assert result.endswith("] (25 items)")
    assert "..." in result
    assert result.startswith("[")


def test_truncate_long_list_without_count():
    """Test that long lists are truncated without count when show_count=False."""
    long_list = list(range(100))
    result = truncate(long_list, max_length=30, show_count=False)

    assert " items)" not in result
    assert "..." in result
    assert result.endswith("]")


def test_truncate_single_item_list():
    """Test that single-item list shows '(1 item)' not '(1 items)'."""
    single_list = ["a very long string that will definitely cause truncation"]
    result = truncate(single_list, max_length=30, show_count=True)

    assert "(1 item)" in result


def test_truncate_empty_list():
    """Test truncating empty list."""
    assert truncate([], max_length=40) == "[]"


def test_truncate_tuple_with_count():
    """Test that tuples are truncated with count."""
    long_tuple = tuple(range(50))
    result = truncate(long_tuple, max_length=30, show_count=True)

    assert result.endswith(") (50 items)")
    assert "..." in result
    assert result.startswith("(")


def test_truncate_nested_structure():
    """Test truncating nested data structures."""
    nested = {"@xmlns:opensearch": "http://a9.com/-/spec/opensearch/1.1/", "data": [{"id": i} for i in range(10)]}
    result = truncate(nested, max_length=40, show_count=True)

    assert "..." in result
    assert result.startswith("{")
    assert result.endswith("} (2 items)")


def test_truncate_custom_object_short_representation():
    """Test truncating custom objects falls back to string representation."""

    class CustomObj:
        def __str__(self):
            return "A CustomObject"

    obj = CustomObj()
    result = truncate(obj, max_length=25)
    assert result == "A CustomObject"


def test_truncate_custom_object_long_representation():
    """Test truncating custom objects falls back to string representation."""

    class CustomObj:
        def __str__(self):
            return "CustomObject with a very long string representation"

    obj = CustomObj()
    result = truncate(obj, max_length=25)

    assert len(result) == 25
    assert "..." in result


def test_truncate_preserves_brackets():
    """Test that closing brackets are preserved in truncated collections."""
    long_dict = {f"key{i}": "value" for i in range(20)}
    result = truncate(long_dict, max_length=30, show_count=False)
    assert result.endswith("}")

    long_list = list(range(100))
    result = truncate(long_list, max_length=30, show_count=False)
    assert result.endswith("]")


def test_truncate_zero_max_length():
    """Test edge case with very small max_length."""
    result = truncate("hello", max_length=5)
    # Should handle gracefully, likely return just suffix or minimal string
    assert len(result) <= 5


@pytest.mark.parametrize("max_length", [10, 20, 30, 40, 50])
def test_truncate_respects_max_length_constraint(max_length):
    """Test that truncated output respects max_length (excluding count suffix)."""
    long_str = "x" * 100
    result = truncate(long_str, max_length=max_length, show_count=False)
    assert len(result) == max_length


def test_truncate_with_processed_response_metadata():
    """Test realistic use case with API response metadata."""
    metadata = {
        "@xmlns:opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "@xmlns:atom": "http://www.w3.org/2005/Atom",
        "totalResults": 1000,
    }
    result = truncate(metadata, max_length=40, show_count=False)

    assert result.startswith("{")
    assert result.endswith("}")
    assert "..." in result
    assert len(result) == 40


def test_truncate_with_processed_response_data():
    """Test realistic use case with API response data."""
    data = [{"id": f"http://arxiv.org/abs/1402.{i:04d}", "title": f"Paper {i}"} for i in range(25)]
    result = truncate(data, max_length=40, show_count=True)

    assert result.startswith("[")
    assert result.endswith("] (25 items)")
    assert "..." in result
