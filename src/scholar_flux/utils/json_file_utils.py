# /utils/json_file_utils.py
"""The scholar_flux.utils.json_file_utils module implements a simple JsonFileUtils class that contains a basic set of
convenience classes for interacting with the file system and JSON files."""
from pathlib import Path
import re
import json
from typing import Union, List, Dict, Any, Generator, Optional

import logging

logger = logging.getLogger(__name__)


class JsonFileUtils:
    """Helper class that implements several basic file utility class methods for easily interacting with the file
    system. This class also contains utility methods used to parse, load, and dump JSON files for convenience.

    Example:
        >>> from scholar_flux.utils.json_file_utils import JsonFileUtils
        >>> from pathlib import Path
        >>> original_data = {"key": "value"}
        >>> json_file = "/tmp/sample"

        # the JSON data should be serializable:
        >>> assert JsonFileUtils.is_jsonable(original_data)
        # writing the json file
        >>> JsonFileUtils.save_as(original_data, json_file)
        # the data should now exist at the '/tmp/sample.json' path
        >>> assert Path(json_file).with_suffix('.json').exists()
        # verifying that the dumped data can be loaded as intended:
        >>> data = JsonFileUtils.load_data(json_file)
        >>> assert data is not None and original_data == data

    """

    DEFAULT_EXT = "json"

    @classmethod
    def get_filepath(cls, filepath: Union[str, Path], ext: Optional[str] = None) -> str:
        """Prepare the filepath using the filepath and extension if provided. Assumes a Unix filesystem structure for
        edge cases.

        Args:
            filepath (Union[str, Path]): The file path to read from
            ext (Optional[str]):
                An optional extension to add to the file path. If the extension is left None, and an extension does
                not yet exist on the file path, the default JSON is used by default.

        """
        filepath_value = Path(filepath).expanduser()

        ext = cls.DEFAULT_EXT if ext is None and not Path(filepath).suffix else ext

        if ext:
            ext = re.sub(r"^\.?", ".", ext)
            filepath_value = filepath_value.with_suffix(ext)
        return str(filepath_value)

    @classmethod
    def save_as(
        cls,
        obj: Union[List, Dict, str, float, int],
        filepath: Union[str, Path],
        ext: Optional[str] = None,
        dump: bool = True,
    ) -> None:
        """Save an object in text format with the specified extension (if provided).

        Args:
            obj (Union[List, Dict, str, float, int]): A value to save into a file
            filepath (Union[str, Path]): The file path to write the object to
            ext (Optional[str]): An optional extension to add to the file path
            dump (bool): If True, the object is serialized using json.dumps. Otherwise the str function is used

        """
        filepath = cls.get_filepath(filepath, ext)
        with open(filepath, "w") as f:
            obj = json.dumps(obj, indent=2) if isinstance(obj, (dict, list)) and dump else str(obj)
            f.write(obj)

    @classmethod
    def load_data(cls, filepath: Union[str, Path], ext: Optional[str] = None) -> Union[Dict, List, str]:
        """Attempts to load data from a filepath as a dictionary/list. If unsuccessful, the file's contents are instead
        loaded as a string.

        Args:
            filepath (Union[str, Path]): The file path to read the data from

        Returns:
            Union[Dict, List, str]:
                A dictionary or list if the data can be successfully loaded with `json`, and a string if loading with
                JSON is not possible.

        """
        filepath = cls.get_filepath(filepath, ext)
        with open(filepath, "r") as f:
            obj = f.read()
        try:
            obj = json.loads(obj)
            logger.debug(f"loaded data from {filepath} as dictionary/list")
        except json.JSONDecodeError as e:
            logger.info(f"Couldn't parse data as JSON: {e}. Loaded data from {filepath} as text")
        return obj

    @classmethod
    def read_lines(cls, filepath: Union[str, Path], ext: Optional[str] = None) -> Generator[str, None, None]:
        """Iteratively reads lines from a text file.

        Args:
            filepath (Union[str, Path]): The file path to read the data from
            ext (Optional[str]): An optional extension to add to the file path

        Returns:
            Generator[str, None, None]: The lines read from a text file

        To retrieve a list of data instead of a generator, pass the result to `list`:
            >>> from scholar_flux.utils import JsonFileUtils
            >>> line_gen = JsonFileUtils.read_lines('pyproject.toml')
            >>> assert isinstance(list(line_gen), list)

        """
        filepath = cls.get_filepath(filepath, ext)
        with open(filepath, "r") as f:
            yield from f

    @classmethod
    def append_to_file(
        cls, content: Union[str, List[str]], filepath: Union[str, Path], ext: Optional[str] = None
    ) -> None:
        """Helper method used to append content to a file in a content-type aware manner.

        Args:
            content (Union[str, List[str]]): The content to append to the file.
            filepath (Union[str, Path]): The file path to write to
            ext (Optional[str]): An optional extension to add to the file path

        """
        filepath = cls.get_filepath(filepath, ext)
        with open(filepath, "a") as f:
            if isinstance(content, list):
                f.writelines(content)
            else:
                f.write(content)

    @staticmethod
    def is_jsonable(obj: Any) -> bool:
        """Verifies whether the object can be serialized as a json object.

        Args:
            obj (Any): The object to check

        Returns:
            bool: True if the object is jsonable (serializable), otherwise False

        """
        try:
            json.dumps(obj)
            return True
        except (TypeError, OverflowError) as e:
            logger.info(f"{e}. Object is not JSON-serializable")
            return False


__all__ = ["JsonFileUtils"]
