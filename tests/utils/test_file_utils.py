from scholar_flux.utils import JsonFileUtils
from types import GeneratorType
from pathlib import Path
import os
import pytest


def test_get_filepath(cleanup, tmp_path):
    """Verifies that the home directory of the user is expanded with the `~/` symbol when defining Paths with
    JsonFileUtils."""
    # Test with ~
    filepath = "~/test.txt"
    ext = ".txt"
    result = JsonFileUtils.get_filepath(filepath, ext)
    expected = os.path.expanduser("~") + "/test.txt"
    assert result == expected

    # Test without extension
    filepath = "test"
    ext = ""
    expected = "test"
    result = JsonFileUtils.get_filepath(filepath, ext)
    assert result == expected


def test_save_as(cleanup, tmp_path):
    """Verifies that saving a file at a path using JsonFileUtils works as intended in saving and identifying saved
    files."""
    obj = {"key": "value"}
    filepath = Path(tmp_path) / "test.json"
    JsonFileUtils.save_as(obj, filepath)
    assert os.path.exists(filepath)


def test_load_data(cleanup, tmp_path):
    """Tests a validates the ability to load files saved with this `save_as` JsonFileUtils class method."""
    # Test with valid JSON
    data = {"key": "value"}
    filepath = Path(tmp_path) / "test.json"
    JsonFileUtils.save_as(data, filepath)
    loaded = JsonFileUtils.load_data(filepath)
    assert loaded == data

    # Test non-JSON content
    content = "non json content"
    filepath = Path(tmp_path) / "test.txt"
    with open(filepath, "w") as f:
        f.write(content)
    loaded = JsonFileUtils.load_data(filepath)
    assert loaded == content


def test_is_jsonable(mock_academic_json):
    """Verifies that dictionaries containing integers, lists, strings, floats.

    can be serialized
    """
    assert JsonFileUtils.is_jsonable({"a": 1})
    assert JsonFileUtils.is_jsonable([1, 2, 3])
    assert JsonFileUtils.is_jsonable(mock_academic_json)  # nested structure of dictionaries, lists, integers, strings
    assert not JsonFileUtils.is_jsonable({1, 2, 3})  # sets are not JSON serializable
    assert not JsonFileUtils.is_jsonable({1: b"a"})  # bytes need to be converted before serialization


def test_read_lines(cleanup, tmp_path):
    """Verifies that the `read_lines` function produces a generator type that can be converted int a list."""
    file_path = tmp_path / "lines.txt"
    lines = ["line1\n", "line2\n", "line3\n"]

    with open(file_path, "w") as f:
        f.writelines(lines)

    gen_result = JsonFileUtils.read_lines(file_path)
    assert isinstance(gen_result, GeneratorType)

    result = list(gen_result)
    assert result == lines


def test_append_to_file(cleanup, tmp_path):
    """Verifies that the `append_to_file function works as intended to append text to files."""
    file_path = tmp_path / "append.txt"
    JsonFileUtils.save_as("start\n", file_path, dump=False)
    JsonFileUtils.append_to_file("middle\n", file_path)
    JsonFileUtils.append_to_file(["end\n"], file_path)
    with open(file_path) as f:
        content = f.readlines()
    assert content == ["start\n", "middle\n", "end\n"]


def test_is_jsonable_logs_on_failure(caplog):
    """Verifies that JsonFileUtils logs unserializable data types when they occur."""

    obj = b"UnserializableType"

    with caplog.at_level("INFO"):
        result = JsonFileUtils.is_jsonable(obj)

    assert not result
    assert "Object is not JSON-serializable" in caplog.text


def test_load_data_invalid_json(tmp_path, cleanup, caplog):
    """Verifies tht, upon attempting to load a bad JSON file, it is loaded as a string if unparsable."""
    file_path = tmp_path / "bad.json"

    with open(file_path, "w") as f:
        f.write("{not: valid json}")

    with caplog.at_level("INFO"):
        result = JsonFileUtils.load_data(file_path)

    assert isinstance(result, str)
    assert "Couldn't parse data as JSON" in caplog.text


def test_read_lines_nonexistent_file(tmp_path, cleanup):
    """When a file doesn't exist at a path, a simple FileNotFoundError should be raised."""
    file_path = tmp_path / "does_not_exist.txt"
    with pytest.raises(FileNotFoundError):
        list(JsonFileUtils.read_lines(file_path))


def test_append_to_file_nonexistent_dir(tmp_path, cleanup):
    """When appending a file path, a simple FileNotFoundError should be raised if the filepath doesn't already exist."""
    # Try to append to a file in a non-existent subdirectory
    file_path = tmp_path / "no_dir" / "file.txt"
    with pytest.raises(FileNotFoundError):
        JsonFileUtils.append_to_file("data", file_path)


def test_save_as_nonserializable_object(tmp_path, cleanup, caplog):
    """Verifies that attempting to save non-serializable components will raise an error on save."""

    file_path = tmp_path / "bad.json"

    obj = b"UnserializableType"

    with caplog.at_level("DEBUG"):
        JsonFileUtils.save_as(obj, file_path)  # type: ignore
    # Should write str(obj), not JSON, and not raise
    with open(file_path) as f:
        content = f.read()
    assert "Unserializable" in content
