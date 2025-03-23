import os
import re
import json
import shutil
from typing import Union, List, Dict

import logging
logger = logging.getLogger(__name__)


class FileUtils:

    @staticmethod
    def get_filepath(filepath: str, ext: str = '') -> str:
        """Prepare the filepath on the basis of the extension and filepath. Assumes a Unix filesystem structure for edge cases."""
        ext = ext if len(ext) == 0 or ext[0] == '.' else f".{ext}"
        filepath = (FileUtils.get_home_directory()+ filepath[1:]).replace("//","/") if filepath[0] == '~' else filepath
        filepath = filepath if filepath[-len(ext):] == ext else f"{filepath}{ext}"
        return filepath

    @staticmethod
    def save_as(obj: Union[List, Dict, str, float, int], filepath: str, ext: str = '',dump=True) -> None:
        """Save an object in text format with the specified extension (if provided)."""
        filepath = FileUtils.get_filepath(filepath, ext)
        with open(filepath, 'w') as f:
            if  isinstance(obj, (dict, list)) and dump:# and FileUtils.is_jsonable(obj):
                obj = json.dumps(obj)
            else:
                obj = str(obj)
            f.write(obj)

    @staticmethod
    def is_jsonable(obj):
        """Check if the object can be serialized as a json object"""
        try:
            json.dumps(obj)
            return True
        except (TypeError, OverflowError) as e:
            logger.debug(f"{e}. Skipping json serialization")
            return False


    @staticmethod
    def load_data(filepath: str, ext: str = '') -> Union[Dict, List, str]:
        """Try loading in data as a dictionary/list. If unsuccessful, return the file contents as a string."""
        filepath = FileUtils.get_filepath(filepath, ext)
        with open(filepath, 'r') as f:
            obj = f.read()
        try:
            obj = json.loads(obj)
            logger.debug(f"loaded data from {filepath} as dictionary/list")
        except json.JSONDecodeError as e:
            logger.debug(f"Couldn't load data as dictionary/list: {e}. Loaded data from {filepath} as text")
        return obj

    @staticmethod
    def file_exists(filepath: str) -> bool:
        """Check if a file exists at the given filepath."""
        return os.path.isfile(filepath)

    @staticmethod
    def delete_file(filepath: str) -> None:
        """Delete a file at the given filepath."""
        if FileUtils.file_exists(filepath):
            os.remove(filepath)
        else:
            logger.warning(f"File {filepath} does not exist.")

    @staticmethod
    def read_lines(filepath: str, ext: str = '') -> List[str]:
        """Read lines from a text file."""
        filepath = FileUtils.get_filepath(filepath, ext)
        with open(filepath, 'r') as f:
            lines = f.readlines()
        return lines

    @staticmethod
    def append_to_file(content: Union[str, List[str]], filepath: str, ext: str = '') -> None:
        """Append content to a file."""
        filepath = FileUtils.get_filepath(filepath, ext)
        with open(filepath, 'a') as f:
            if isinstance(content, list):
                f.writelines(content)
            else:
                f.write(content)

    @staticmethod
    def copy_file(src: str, dst: str) -> None:
        """Copy a file from src to dst."""
        shutil.copy(src, dst)

    @staticmethod
    def move_file(src: str, dst: str) -> None:
        """Move or rename a file from src to dst."""
        shutil.move(src, dst)

    @staticmethod
    def get_file_size(filepath: str) -> int:
        """Get the size of a file in bytes."""
        return os.path.getsize(filepath)

    @staticmethod
    def list_files(directory: str) -> List[str]:
        """List all files in a given directory."""
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    @staticmethod
    def create_directory(directory: str) -> None:
        """Create a directory if it does not exist."""
        os.makedirs(directory, exist_ok=True)

    @staticmethod
    def get_file_extension(filepath: str) -> str:
        """Get the file extension of the given file."""
        return os.path.splitext(filepath)[1]
    @staticmethod
    def get_home_directory() -> str:
        """Get the path to the home directory."""
        return os.path.expanduser("~") + '/'


# Usage example
# FileUtils.save_as({"key": "value"}, "example", "json")
# data = FileUtils.load_data("example.json")

