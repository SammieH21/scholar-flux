# /utils/json_processing_utils.py
"""
Helper module used to process recursive JSON data received from APIs of an unknown type and structure.

Classes:
    PathUtils: Utility class used to prepare path strings and lists of path components consistently for processing.
    KeyDiscoverer: Helper class for identifying JSON paths and terminal keys containing nested data elements.
    KeyFilter: Helper class used to identify and filter nested dictionaries based on path length and pattern matching.
    RecursiveJsonProcessor: Front-end facing utility function used by the `scholar_flux.data.RecursiveDataProcessor`
                            to process, filter, and flatten JSON formatted data.
    JsonRecordData: Helper class used as a container to hold extracted path/data components for further processing.
    JsonNormalizer: Helper class used by the `RecursiveJsonProcessor` to flatten the inputted JSON record into a
                    non-nested dictionary

Example Use:
    >>> from scholar_flux.utils import RecursiveJsonProcessor
    >>> from pprint import pp
    >>> data = {
            "authors": {"principle_investigator": "Dr. Smith", "assistant": "Jane Doe"},
            "doi": "10.1234/example.doi",
            "title": "Sample Study",
            "abstract": ["This is a sample abstract.", "keywords: 'sample', 'abstract'"],
            "genre": {"subspecialty": "Neuroscience"},
            "journal": {"topic": "Sleep Research"},
        }
    # joins fields with nested components using a newline character - retains full paths leading to each value
    >>> processor = RecursiveJsonProcessor(object_delimiter = '   ', use_full_path = True)
    # processes and flattens the JSON dict using the defined helper classes under the hood
    >>> result = processor.process_and_flatten(data)
    # prints the result in a format that is easier to view from the CLI
    >>> pp(result)
    # OUTPUT: {'authors.principle_investigator': 'Dr. Smith',
               'authors.assistant': 'Jane Doe',
               'doi': '10.1234/example.doi',
               'title': 'Sample Study',
               'abstract': "This is a sample abstract.   keywords: 'sample', 'abstract'",
               'genre.subspecialty': 'Neuroscience',
               'journal.topic': 'Sleep Research'}
"""
from typing import Dict, List, Tuple, Any, Optional
from itertools import chain
from dataclasses import dataclass
import re

from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class PathUtils:
    """
    Helper class used to perform string/list manipulations for paths that can be represented
    in either form, requiring conversion from one type to the other in specific JSON path processing
    scenarios.
    """

    @staticmethod
    def path_name(level_names: List[Any]) -> str:
        """
        Generate a string representation of the path based on the provided level names.

        Args:
            level_names (List[Any]): A list of names representing the path levels.

        Returns:
            str: A string representation of the path.
        """
        logger.debug(f"Generating path name for levels: {level_names}")

        if not level_names:
            return ""
        for name in reversed(level_names):
            if not isinstance(name, int):
                logger.debug(f"Found non-integer name: {name}")
                return str(name)
        path_str = PathUtils.path_str(level_names)
        return path_str

    @staticmethod
    def path_str(level_names: List[Any]) -> str:
        """
        Join the level names into a single string separated by underscores.

        Args:
            level_names (List[Any]): A list of names representing the path levels.

        Returns:
           str: A single string with level names joined by underscores.
        """
        path_str = ".".join(map(str, level_names))
        return path_str

    @staticmethod
    def remove_path_indices(path: List[Any]) -> List[Any]:
        """
        Remove integer indices from the path to get a list of key names.

        Args:
            path (List[Any]): The original path containing both keys and indices.

        Returns:
            List[Any]: A path with only the key names.
        """
        key_path = [k for k in path if not isinstance(k, int) and k not in ("value",)]
        return key_path

    @staticmethod
    def constant_path_indices(path: List[Any], constant: str = "i") -> List[Any]:
        """
        Replace integer indices with constants in the provided path.

        Args:
            path (List[Any]): The original path containing both keys and indices.
            constant (str): A value to replace a numeric value with.

        Returns:
            List[Any]: A path with only the key names.
        """
        constant = constant or "i"
        key_path = [constant if isinstance(k, int) else k for k in path]
        return key_path

    @staticmethod
    def group_path_assignments(path: List[Any]) -> Optional[str]:
        """
        Group the path assignments into a single string, excluding indices.

        Args:
            path (List[Any]): The original path containing both keys and indices.

        Returns:
            Optional[str]: A single string representing the grouped path, or None if the path is empty.
        """
        key_path = PathUtils.constant_path_indices(path)
        if key_path:
            grouped_path = PathUtils.path_str(key_path)
            return grouped_path
        logger.debug("No valid keys found in path")
        return None


class KeyFilter:
    """
    Helper class used to create a simple filter that allows for the identification of terminal keys
    associated with data in a JSON structure and the paths that lead to each terminal key.
    """

    @staticmethod
    def filter_keys(
        discovered_keys: Dict[str, List[str]],
        prefix: Optional[str] = None,
        min_length: Optional[int] = None,
        substring: Optional[str] = None,
        pattern: Optional[str] = None,
        include_matches: bool = True,
        match_any: bool = True,
    ) -> Dict[str, List[str]]:
        """
        A method used to create a function that matches key-value pairs based on the specified criteria.
        For example, filtering can be configured to identify keys based on prefix, minimum path length,
        and path substring/pattern matching with conditional match inclusion/exclusion.
        """

        def matches_criteria(key: str, paths: List[str]) -> bool:
            """
            Helper function that, when configured via `filter_keys` allows for the identification
            of keys and paths that match a specific criteria
            """
            matches = []
            if prefix:
                matches.append(key.startswith(prefix))
            if min_length is not None:
                matches.append(any(len(path.split(".")) >= min_length for path in paths))
            if substring:
                matches.append(any(substring in path for path in paths))
            if pattern:
                regex_pattern = re.compile(pattern)
                matches.append(any(regex_pattern.fullmatch(node) for path in paths for node in path.split(".")))
            fn = any if match_any else all

            return fn(matches)

        return {key: paths for key, paths in discovered_keys.items() if matches_criteria(key, paths) is include_matches}


class KeyDiscoverer:
    """
    Helper class used to discover terminal keys containing data within nested JSON data structures and
    identify the paths used to arrive at each key.

    Attributes:
        _discovered_keys (dict[str, list]): Defines the complete list of all keys that can be found in a dictionary
                                            and the path that needs to be traversed to arrive at that key
        _terminal_paths (dict[str, bool]): Creates a dictionary that indicates whether the currently added path is
                                           terminal within the JSON data structure
    """

    def __init__(self, records: Optional[List[Dict]] = None):
        """Initializes the KeyDiscoverer and identifies terminal key/path pairs within the JSON data structure"""
        self.records = records or []
        self._discovered_keys, self._terminal_paths = self._discover_keys()

    def _discover_keys(self) -> Tuple[Dict[str, List[str]], Dict[str, bool]]:
        """Discovers all keys within the provided records recursively."""
        discovered_keys: dict[str, list] = defaultdict(list)
        terminal_paths: dict[str, bool] = {}
        for record in self.records:
            self._discover_keys_recursive(record, discovered_keys, terminal_paths, [])
        return discovered_keys, terminal_paths

    def _is_terminal(self, value: Any) -> bool:
        """Determines if the given value is terminal (not a nested dictionary or a list with nested dictionaries)."""
        if isinstance(value, dict):
            return False
        if isinstance(value, list):
            # Check recursively if there are any dictionaries within the list
            return all(self._is_terminal(item) for item in value)
        return True

    def _discover_keys_recursive(
        self,
        record: Any,
        discovered_keys: Dict[str, List[str]],
        terminal_paths: Dict[str, bool],
        current_path: List[str],
    ) -> None:
        """Recursively traverses records to discover keys, their paths, and terminal status."""
        if isinstance(record, dict):
            for key, value in record.items():
                new_path = current_path + [key]
                path_str = PathUtils.path_str(new_path)
                if path_str not in discovered_keys[key]:
                    discovered_keys[key].append(path_str)
                self._discover_keys_recursive(value, discovered_keys, terminal_paths, new_path)
                terminal_paths[path_str] = self._is_terminal(value)
        elif isinstance(record, list):
            for index, item in enumerate(record):
                new_path = current_path + [str(index)]
                self._discover_keys_recursive(item, discovered_keys, terminal_paths, new_path)

    def get_all_keys(self) -> Dict[str, List[str]]:
        """Returns all discovered keys and their paths."""
        return self._discovered_keys

    def get_terminal_keys(self) -> Dict[str, List[str]]:
        """Returns keys and their terminal paths (paths that don't contain nested dictionaries)."""
        terminal_keys = defaultdict(list)
        for path, is_terminal in self._terminal_paths.items():
            if is_terminal:
                key = path.split(".")[-1]
                terminal_keys[key].append(path)
        return terminal_keys

    def get_terminal_paths(self) -> List[str]:
        """Returns paths indicating whether they are terminal (don't contain nested dictionaries)."""
        return [path for (path, is_terminal) in self._terminal_paths.items() if is_terminal]

    def get_keys_with_path(self, key: str) -> List[str]:
        """Returns all paths associated with a specific key."""
        return self._discovered_keys.get(key, [])

    def filter_keys(
        self,
        prefix: Optional[str] = None,
        min_length: Optional[int] = None,
        substring: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Helper method that filters a range of keys based on the specified criteria"""
        return KeyFilter.filter_keys(self._discovered_keys, prefix, min_length, substring)

    def __repr__(self) -> str:
        """Helper method for displaying a human-readable representation of the KeyDiscoverer"""
        class_name = self.__class__.__name__

        return (
            f"{class_name}(records=len({len(self.records)}), "
            f"_discovered_keys=len({len(self._discovered_keys)}), "
            f"_terminal_paths=len({len(self._terminal_paths)}))"
        )


@dataclass
class JsonRecordData:
    """
    Helper class used as a container to record the paths, data, and names associated with each terminal path.

    Args:
        path (list[str | int]): The path associated with the terminal data point where nested terminal values can be found
        data (dict[str, Any]): The nested terminal value at the end of a path

    """

    path: List[str | int]
    data: Dict[str, Any]


class RecursiveJsonProcessor:
    """
    An implementation of a recursive JSON dictionary processor that is used
    to process and identify nested components such as paths, terminal key names, and
    the data at each terminal path.

    This utility of the RecursiveJsonProcessor is for flattening dictionary records
    into flattened representations where its keys represent the terminal paths at each
    node and its values represent the data found at each terminal path.
    """

    def __init__(
        self,
        json_dict: Optional[Dict] = None,
        object_delimiter: Optional[str] = "; ",
        normalizing_delimiter: Optional[str] = None,
        use_full_path: Optional[bool] = False,
    ):
        """
        Initialize the RecursiveJsonProcessor with a JSON dictionary and a delimiter for joining list elements.

        Args:
            json_dict (Dict): The input JSON dictionary to be parsed.
            object_delimiter (str): The delimiter used to join elements max depth list objects. Default is "; ".
            normalizing_delimiter (str): The delimiter used to join elements across multiple keys when normalizing. Default is "\n\n".
        """
        self.json_dict = json_dict
        self.normalizing_delimiter = normalizing_delimiter
        self.object_delimiter = object_delimiter
        self.key_discoverer = (
            KeyDiscoverer([json_dict] if not isinstance(json_dict, list) else json_dict) if json_dict else None
        )
        self.use_full_path = use_full_path or False
        self.extracted_record_data_list: list[JsonRecordData] = []

    def combine_normalized(self, normalized_field_value: Optional[list | str]) -> list | str | None:
        """
        Combines lists of nested data (strings, ints, None, etc.) into a single string separated by
        the normalizing_delimiter. If a delimiter isn't specified or if the value is None, it is
        returned as is without modification.
        """
        if isinstance(normalized_field_value, str):
            return normalized_field_value
        if self.normalizing_delimiter is not None and isinstance(normalized_field_value, list):
            return (
                self.normalizing_delimiter.join([f"{value}" for value in normalized_field_value if value is not None])
                or None
            )
        return self.unlist(normalized_field_value)

    @staticmethod
    def unlist(current_data: Optional[Dict | List]) -> Optional[Any]:
        """
        Flattens a dictionary or list if it contains a single element that is a dictionary.

        Args:
            current_data: A dictionary or list to be flattened if it contains a single dictionary element.

        Returns:
            Optional[Dict|List]: The flattened dictionary if the input meets the flattening condition, otherwise returns the input unchanged.
        """
        if isinstance(current_data, list) and len(current_data) == 1:
            return current_data[0]
        return current_data

    def process_dictionary(self, obj: Optional[Dict] = None):
        """Create a new json dictionary that contains information about the relative paths of each
        field that can be found within the current json_dict.
        """
        self.json_dict = obj or self.json_dict
        if not self.json_dict:
            raise ValueError("Json Dictionary not specified")
        self.extracted_record_data_list.clear()
        self.process_level(self.json_dict)
        return self

    def process_level(self, obj: Any, level_name: Optional[List[Any]] = None) -> List[Any]:
        """
        Helper method for processing a level within a dictionary. This method is recursively called
        to process nested components
        """
        level_name = level_name if level_name is not None else []
        if isinstance(obj, list):
            if any(isinstance(v_i, (list, dict)) for v_i in obj):
                return list(chain.from_iterable(self.process_level(v_i, level_name + [i]) for i, v_i in enumerate(obj)))
            joined_obj = self.object_delimiter.join(map(str, obj)) if self.object_delimiter is not None else tuple(obj)
            return self.process_level(joined_obj, level_name)
        elif isinstance(obj, dict):
            return list(chain.from_iterable(self.process_level(v, level_name + [k]) for k, v in obj.items()))
        else:
            obj = list(obj) if isinstance(obj, tuple) else obj
            obj_info = JsonRecordData(data=obj, path=level_name)
            self.extracted_record_data_list.append(obj_info)
            return [obj_info]

    def filter_extracted(self, exclude_keys: Optional[List[str]] = None):
        """
        Filter the extracted JSON dictionaries to exclude specified keys.

        Args:
            exclude_keys ([List[str]]): List of keys to exclude from the flattened result.
        """

        self.extracted_record_data_list = (
            [obj for obj in self.extracted_record_data_list if not any(key in set(exclude_keys) for key in obj.path)]
            if exclude_keys
            else self.extracted_record_data_list
        )

        return self

    def flatten(self) -> Optional[Dict[str, List[Any] | str | None]]:
        """
        Flatten the extracted JSON dictionary from a nested structure into a simpler structure.

        Returns:
            Optional[Dict[str, List[Any]]]: A dictionary with flattened paths as keys and lists of values.
        """

        if self.extracted_record_data_list:
            normalizer = JsonNormalizer(
                self.extracted_record_data_list,
                use_full_path=self.use_full_path,
            )
            normalized_json = normalizer.normalize_extracted()
            normalized_json = {
                data_key: self.combine_normalized(field_value) for data_key, field_value in normalized_json.items()
            }
            return normalized_json

        logger.debug("No data extracted, returning None")
        return None

    def process_and_flatten(
        self, obj: Optional[Dict] = None, exclude_keys: Optional[List[str]] = None
    ) -> Optional[Dict[str, List[Any] | str | None]]:
        """
        Process the dictionary, filter extracted paths, and then flatten the result.

        Args:
            exclude_keys (Optional[List[str]]): List of keys to exclude from the flattened result.

        Returns:
            Optional[Dict[str, List[Any]]]: A dictionary with flattened paths as keys and lists of values.
        """
        self.process_dictionary(obj)
        if exclude_keys:
            self.filter_extracted(exclude_keys)
        return self.flatten()

    def __repr__(self) -> str:
        """Helper method for displaying a human-readable representation of the RecursiveJsonProcessor"""
        class_name = self.__class__.__name__

        return f"{class_name}(object_delimiter={self.object_delimiter}, simplifier={self.normalizing_delimiter}, use_full_path={self.use_full_path})"


class JsonNormalizer:
    """Helper class that flattens and normalizes the retrieved list of JsonRecordData into singular flattened dictionary"""

    def __init__(
        self,
        json_record_data_list: List[JsonRecordData],
        use_full_path: bool = False,
    ):
        """
        Initialize the JsonNormalizer with extracted JSON data and a delimiter.

        Args:
            extracted_record_data_list (List[JsonRecordData]): The list of extracted JSON data.
            delimiter (str): The delimiter used to join elements in lists.
            use_full_path (str): Indicates whether to use the full nested json path or the smallest unique path available
        """

        self.json_record_data_list = json_record_data_list
        self.use_full_path = use_full_path or False

    def normalize_extracted(self) -> Dict[str, List[Any] | str | None]:
        """
        Normalize the extracted JSON data into a flattened dictionary.

        Returns:
            Dict[str, List[Any]]: A dictionary with flattened paths as keys and lists of values.
        """
        logger.debug("Starting normalization process")
        flattened_json_dict: dict = defaultdict(list)
        unique_mappings_dict: dict = defaultdict(list)

        for json_record_data in self.json_record_data_list:
            current_obj, current_path = json_record_data.data, json_record_data.path
            current_group = PathUtils.remove_path_indices(current_path)
            current_key_str = ".".join(current_group)

            if not current_group:
                logger.debug(f"Skipping empty group for path: {current_path}")
                continue

            current_data_key = self.get_unique_key(current_key_str, current_group, unique_mappings_dict)
            flattened_json_dict[current_data_key].append(current_obj)
            logger.debug(f"Added data to key {current_data_key}: {str(current_obj)}")

        logger.debug("Normalization process completed")
        return flattened_json_dict

    def get_unique_key(
        self,
        current_key_str: str,
        current_group: List[str],
        unique_mappings_dict: Dict[str, List[str]],
    ) -> str:
        """
        Generate a unique key for the current data entry.

        Args:
            current_key_str (str): The string representation of the current path.
            current_group (List[str]): The list of keys in the current path.
            unique_mappings_dict (Dict[str, List[str]]): A dictionary tracking unique keys.

        Returns:
            str: A unique key for the current data entry.
        """
        logger.debug(f"Generating unique key for: {current_key_str}")

        found_key = next(
            (data_key for data_key, key_str in unique_mappings_dict.items() if current_key_str in key_str),
            None,
        )

        if found_key:
            return found_key

        return self.create_unique_key(current_group, current_key_str, unique_mappings_dict)

    def create_unique_key(
        self,
        current_group: List[str],
        current_key_str: str,
        unique_mappings_dict: Dict[str, List[str]],
    ) -> str:
        """
        Create a unique key for the current data entry if a simple key is not sufficient.

        Args:
            current_group (List[str]): The list of keys in the current path.
            current_key_str (str): The string representation of the current path.
            unique_mappings_dict (Dict[str, List[str]]): A dictionary tracking unique keys.

        Returns:
            str: A unique key for the current data entry.
        """
        idx = 1 if not self.use_full_path else len(current_group)
        while idx <= len(current_group):
            current_data_key_test = ".".join(current_group[-idx:])
            if current_data_key_test not in unique_mappings_dict:
                unique_mappings_dict[current_data_key_test].append(current_key_str)
                logger.debug(f"Created unique key: {current_key_str} => {current_data_key_test}")
                return current_data_key_test
            idx += 1

        idx = 1
        base_key = current_group[-1]
        current_data_key_test = f"{base_key}.{idx}"
        while current_data_key_test in unique_mappings_dict:
            idx += 1
            current_data_key_test = f"{base_key}.{idx}"

        unique_mappings_dict[current_data_key_test].append(current_key_str)
        logger.debug(f"Created unique key: {current_key_str} => {current_data_key_test}")
        return current_data_key_test


__all__ = [
    "PathUtils",
    "KeyDiscoverer",
    "KeyFilter",
    "RecursiveJsonProcessor",
    "JsonRecordData",
    "JsonNormalizer",
]
