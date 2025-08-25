from scholar_flux.utils import FileUtils


import pytest
import os
import json
from unittest.mock import patch, MagicMock
import pytest
from scholar_flux.utils.file_utils import FileUtils


def test_get_filepath(cleanup, tmp_path):
    # Test with ~
    filepath = "~test.txt"
    ext = ".txt"
    expected = os.path.expanduser("~") + "/test.txt"
    result = FileUtils.get_filepath(filepath, ext)
    assert result == expected

    # Test without extension
    filepath = "test"
    ext = ""
    expected = "test"
    result = FileUtils.get_filepath(filepath, ext)
    assert result == expected

def test_save_as(cleanup, tmp_path):
    obj = {"key": "value"}
    filepath = os.path.join(tmp_path, "test.json")
    FileUtils.save_as(obj, filepath)
    assert os.path.exists(filepath)

def test_load_data(cleanup, tmp_path):
    # Test with valid JSON
    data = {"key": "value"}
    filepath = os.path.join(tmp_path, "test.json")
    FileUtils.save_as(data, filepath)
    loaded = FileUtils.load_data(filepath)
    assert loaded == data

    # Test non-JSON content
    content = "non json content"
    filepath = os.path.join(tmp_path, "test.txt")
    with open(filepath, 'w') as f:
        f.write(content)
    loaded = FileUtils.load_data(filepath)
    assert loaded == content

def test_file_exists(cleanup, tmp_path):
    # Test existing file
    filepath = os.path.join(tmp_path, "test.json")
    FileUtils.save_as({}, filepath)
    assert FileUtils.file_exists(filepath)

    # Test non-existing file
    non_existing = os.path.join(tmp_path, "non_exist.txt")
    assert not FileUtils.file_exists(non_existing)

def test_delete_file(cleanup, tmp_path):
    # Create a file to delete
    filepath = os.path.join(tmp_path, "test.json")
    FileUtils.save_as({}, filepath)
    assert os.path.exists(filepath)

    FileUtils.delete_file(filepath)
    assert not os.path.exists(filepath)

# Additional tests for other methods can be written similarly.

