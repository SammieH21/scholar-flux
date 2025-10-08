from scholar_flux.utils import FileUtils
from pathlib import Path
import os


def test_get_filepath(cleanup, tmp_path):
    """
    Verifies that the home directory of the user is expanded with the `~/` symbol when defining Paths with FileUtils.
    """
    # Test with ~
    filepath = "~/test.txt"
    ext = ".txt"
    result = FileUtils.get_filepath(filepath, ext)
    expected = os.path.expanduser("~") + "/test.txt"
    assert result == expected

    # test using the FileUtils home directory:
    result = FileUtils.get_home_directory() + "test.txt"
    assert result == expected

    # Test without extension
    filepath = "test"
    ext = ""
    expected = "test"
    result = FileUtils.get_filepath(filepath, ext)
    assert result == expected


def test_save_as(cleanup, tmp_path):
    """Verifies that saving a file at a path using FileUtils works as intended in saving and identifying saved files"""
    obj = {"key": "value"}
    filepath = Path(tmp_path) / "test.json"
    FileUtils.save_as(obj, filepath)
    assert os.path.exists(filepath)


def test_load_data(cleanup, tmp_path):
    """Tests a validates the ability to load files saved with this `save_as` FileUtils class method"""
    # Test with valid JSON
    data = {"key": "value"}
    filepath = Path(tmp_path) / "test.json"
    FileUtils.save_as(data, filepath)
    loaded = FileUtils.load_data(filepath)
    assert loaded == data

    # Test non-JSON content
    content = "non json content"
    filepath = Path(tmp_path) / "test.txt"
    with open(filepath, "w") as f:
        f.write(content)
    loaded = FileUtils.load_data(filepath)
    assert loaded == content


def test_file_exists(cleanup, tmp_path):
    """Verifies that the `file_exists` tool can be used from the FileUtils helper class to find saved files"""
    # Test existing file
    filepath = Path(tmp_path) / "test.json"
    FileUtils.save_as({}, filepath)
    assert FileUtils.file_exists(filepath)

    # Test non-existing file
    non_existing = os.path.join(tmp_path, "non_exist.txt")
    assert not FileUtils.file_exists(non_existing)


def test_delete_file(cleanup, tmp_path):
    """Verifies that a file that exists can also be deleted with te `delete_file` method"""
    # Create a file to delete
    filepath = os.path.join(tmp_path, "test.json")
    FileUtils.save_as({}, filepath)
    assert os.path.exists(filepath)

    FileUtils.delete_file(filepath)
    assert not os.path.exists(filepath)


def test_show_dir(cleanup, tmp_path):
    """Verifies that a list of json files can be created from a simple empty dictionary"""
    files = [f"file{i}.json" for i in range(1, 6)]
    obj = {"key": "value"}
    for file_name in files:
        filepath = Path(tmp_path) / file_name
        FileUtils.save_as(obj, filepath)

    file_list = FileUtils.list_files(tmp_path)
    assert all(file in file_list for file in files)


def test_get_file_size(cleanup, tmp_path):
    """Verifies that the size of a file is quickly retrievable via `FileUtils.get_file_size`"""
    # Create a file with known content
    content = "test content"
    filepath = Path(tmp_path) / "test.txt"

    FileUtils.save_as(content, filepath)

    # Get the size of the file
    size = FileUtils.get_file_size(filepath)
    assert size == len(content)
