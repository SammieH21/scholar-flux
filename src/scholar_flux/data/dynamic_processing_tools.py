from typing import Dict, List, Tuple, Any, Optional
import itertools
from itertools import chain
import re

import pandas as pd
from collections import defaultdict
import logging
logger = logging.getLogger(__name__)

class PathUtils:
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
        logger.debug(f"Generated path string: {path_str}")
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
        logger.debug(f"Joining path levels: {level_names}")
        path_str = ".".join(map(str, level_names))
        logger.debug(f"Joined path string: {path_str}")
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
        logger.debug(f"Removing indices from path: {path}")
        key_path = [k for k in path if not isinstance(k, int) and k not in ('value')]
        logger.debug(f"Path without indices: {key_path}")
        return key_path

    @staticmethod
    def constant_path_indices(path: List[Any]) -> List[Any]:
        """
        Replace integer indices with constants in the provided path.
        
        Args:
            path (List[Any]): The original path containing both keys and indices.
        
        Returns:
            List[Any]: A path with only the key names.
        """
        key_path = ['i' if isinstance(k,int) else k for k in path]
        logger.debug(f"constant path indices: {key_path}")
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
        logger.debug(f"Grouping path assignments for path: {path}")
        key_path = PathUtils.constant_path_indices(path)
        if key_path:
            grouped_path = PathUtils.path_str(key_path)
            logger.debug(f"Grouped path: {grouped_path}")
            return grouped_path
        logger.debug("No valid keys found in path")
        return None

class KeyFilter:
    @staticmethod
    def filter_keys(
        discovered_keys: Dict[str, List[str]], 
        prefix: Optional[str] = None, 
        min_length: Optional[int] = None, 
        substring: Optional[str] = None, 
        pattern: Optional[str] = None, 
        include_matches: bool = True
    ) -> Dict[str, List[str]]:
        def matches_criteria(key: str, paths: List[str]) -> bool:
            if prefix and key.startswith(prefix):
                return True
            if min_length is not None and any(len(path.split(".")) >= min_length for path in paths):
                return True
            if substring and any(substring in path for path in paths):
                return True
            if pattern:
                regex_pattern = re.compile(pattern)
                if any(regex_pattern.fullmatch(node) for path in paths for node in path.split(".")):
                    return True
            return False

        return {key: paths for key, paths in discovered_keys.items() if matches_criteria(key, paths) == include_matches}


class KeyDiscoverer:
    def __init__(self, records: List[Dict]):
        self.records = records
        self._discovered_keys, self._terminal_paths = self._discover_keys()

    def _discover_keys(self) -> Tuple[Dict[str, List[str]], Dict[str, bool]]:
        """Discovers all keys within the provided records recursively."""
        discovered_keys = defaultdict(list)
        terminal_paths = {}
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

    def _discover_keys_recursive(self, record: Any, discovered_keys: Dict[str, List[str]], terminal_paths: Dict[str, bool], current_path: List[str]) -> None:
        """Recursively traverses records to discover keys, their paths, and terminal status."""
        if isinstance(record, dict):
            for key, value in record.items():
                new_path = current_path + [key]
                path_str = PathUtils.path_str(new_path)
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
                key = path.split('.')[-1]
                terminal_keys[key].append(path)
        return terminal_keys

    def get_terminal_paths(self) -> List[str]:
        """Returns paths indicating whether they are terminal (don't contain nested dictionaries)."""
        return [path for (path, is_terminal) in self._terminal_paths.items() if is_terminal]

    def get_keys_with_path(self, key: str) -> List[str]:
        """Returns all paths associated with a specific key."""
        return self._discovered_keys.get(key, [])

    def filter_keys(self, prefix: Optional[str] = None, min_length: Optional[int] = None, substring: Optional[str] = None) -> Dict[str, List[str]]:
        return KeyFilter.filter_keys(self._discovered_keys, prefix, min_length, substring)

class DynamicDictProcessor:
    def __init__(self, json_dict: Optional[Dict] = None, delimiter: Optional[str] = None, obj_delimiter: str= "; "):
        """
        Initialize the DynamicDictProcessor with a JSON dictionary and a delimiter for joining list elements.

        Args:
            json_dict (Dict): The input JSON dictionary to be parsed.
            delimiter (str): The delimiter used to join elements across multiple keys when normalizing. Default is "\n\n".
            obj_delimiter (str): The delimiter used to join elements max depth list objects. Default is "; ".
        """
        self.json_dict = json_dict
        self.json_extracted = []
        self.delimiter = delimiter
        self.obj_delimiter = obj_delimiter
        self.key_discoverer = KeyDiscoverer([json_dict])
        
    def combine_normalized(self,normalized_field_value:Optional[List]):
        if self.delimiter is not None and isinstance(normalized_field_value,list):
            return self.delimiter.join(normalized_field_value)
        return self.unlist(normalized_field_value)

    @staticmethod
    def unlist(current_data: Optional[Dict|List]) -> Optional[Any]:
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

    def process_dictionary(self,obj: Optional[Dict] = None):
        """ create a new json dictionary that contains information about the relative paths of each
            field that can be found within the current json_dict.
        """
        self.json_dict = obj or self.json_dict
        if not self.json_dict:
            raise ValueError("Json Dictionary not specified")
        logger.info("Starting flattening process")
        self.json_extracted.clear()
        self.process_level(self.json_dict)
        return self

####def process_level(self, obj: Any, level_name: Optional[List[Any]] = None) -> List[Any]:
####    """
####    Recursively process each level of the JSON dictionary to extract data and paths.

####    Args:
####        obj (Any): The current level of the JSON object being processed.
####        level_name (Optional[List[Any]]): The current path in the JSON object.

####    Returns:
####        List[Any]: A list of processed levels.
####    """
####    level_name = level_name if level_name is not None else []
####    if isinstance(obj, list):
####        logger.debug(f"Processing list at path: {level_name}")
####        if any(isinstance(v_i, (list, dict)) for v_i in obj):
####            return [self.process_level(v_i, level_name + [i]) for i, v_i in enumerate(obj)]
####        joined_obj = self.obj_delimiter.join(map(str, obj))
####        return self.process_level(joined_obj, level_name)
####    elif isinstance(obj, dict):
####        logger.debug(f"Processing dictionary at path: {level_name}")
####        return [self.process_level(v, level_name + [k]) for k, v in obj.items()]
####    else:
####        fmt_name = PathUtils.path_name(level_name)
####        obj_info = {'data': obj, 'path': level_name, 'last_key': fmt_name}
####        self.json_extracted.append(obj_info)
####        logger.debug(f"Extracted data: {obj_info}")
####        return [obj_info]

    def process_level(self, obj: Any, level_name: Optional[List[Any]] = None) -> List[Any]:
        level_name = level_name if level_name is not None else []
        if isinstance(obj, list):
            if any(isinstance(v_i, (list, dict)) for v_i in obj):
                return list(chain.from_iterable(self.process_level(v_i, level_name + [i]) for i, v_i in enumerate(obj)))
            joined_obj = self.obj_delimiter.join(map(str, obj))
            return self.process_level(joined_obj, level_name)
        elif isinstance(obj, dict):
            return list(chain.from_iterable(self.process_level(v, level_name + [k]) for k, v in obj.items()))
        else:
            fmt_name = PathUtils.group_path_assignments(level_name)
            obj_info = {'data': obj, 'path': level_name, 'last_key': fmt_name}
            self.json_extracted.append(obj_info)
            return [obj_info]

    def filter_extracted(self, exclude_keys: Optional[List[str]] = None):
        """
        Filter the extracted JSON dictionaries to exclude specified keys.

        Args:
            exclude_keys ([List[str]]): List of keys to exclude from the flattened result.
        """

        self.json_extracted = [
            obj for obj in self.json_extracted
            if not any(key in set(exclude_keys) for key in obj['path'])
        ] if exclude_keys else self.json_extracted

        return self

    def flatten(self) -> Optional[Dict[str, List[Any]]]:
        """
        Flatten the extracted JSON dictionary from a nested structure into a simpler structure.

        Returns:
            Optional[Dict[str, List[Any]]]: A dictionary with flattened paths as keys and lists of values.
        """

        if self.json_extracted:
            logger.info("Normalization process started")
            normalizer = JsonNormalizer([json_extraction['data'] for json_extraction in self.json_extracted],
                                        [json_extraction['path'] for json_extraction in self.json_extracted])
            normalized_json = normalizer.normalize_extracted()
            normalized_json = {data_key: self.combine_normalized(field_value)
                               for data_key, field_value in normalized_json.items()}
            return normalized_json
            
        logger.info("No data extracted, returning None")
        return None

    def process_and_flatten(self,obj: Optional[Dict] = None,exclude_keys: Optional[List[str]] = None) -> Optional[Dict[str, List[Any]]]:
        """
        Process the dictionary, filter extracted paths, and then flatten the result.

        Args:
            exclude_keys (Optional[List[str]]): List of keys to exclude from the flattened result.

        Returns:
            Optional[Dict[str, List[Any]]]: A dictionary with flattened paths as keys and lists of values.
        """
        self.process_dictionary(obj)
        self.filter_extracted(exclude_keys)
        return self.flatten()


class JsonNormalizer:
    def __init__(self, json_extracted_dicts: List[Dict[str, Any]],json_extracted_paths: List[List]):
        """
        Initialize the JsonNormalizer with extracted JSON data and a delimiter.

        Args:
            json_extracted (List[Dict[str, Any]]): The list of extracted JSON data.
            delimiter (str): The delimiter used to join elements in lists.
        """

        if not len(json_extracted_dicts) == len(json_extracted_paths):
            raise ValueError("Extracted Dicts and Paths not of the same length, {len(json_extracted_dicts)} != {len(json_extracted_paths)}") 
        self.json_extracted_dicts = json_extracted_dicts
        self.json_extracted_paths = json_extracted_paths

    def normalize_extracted(self) -> Dict[str, List[Any]]:
        """
        Normalize the extracted JSON data into a flattened dictionary.

        Returns:
            Dict[str, List[Any]]: A dictionary with flattened paths as keys and lists of values.
        """
        logger.info("Starting normalization process")
        flattened_json_dict = defaultdict(list)
        unique_mappings_dict = defaultdict(list)


        for current_obj, current_path in zip(self.json_extracted_dicts, self.json_extracted_paths):
            current_group = PathUtils.remove_path_indices(current_path)
            current_key_str = '.'.join(current_group) if current_group else None

            if not current_group:
                logger.debug(f"Skipping empty group for path: {current_path}")
                continue

            current_data_key = self.get_unique_key(current_key_str, current_group, unique_mappings_dict)
            flattened_json_dict[current_data_key].append(str(current_obj))
            logger.debug(f"Added data to key {current_data_key}: {str(current_obj)}")

        logger.info("Normalization process completed")
        return flattened_json_dict

    def get_unique_key(self, current_key_str: str, current_group: List[str], unique_mappings_dict: Dict[str, List[str]]) -> str:
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

        found_key = next((data_key for data_key, key_str in unique_mappings_dict.items() if current_key_str in key_str), None)

        if found_key:
            logger.debug(f"Found existing key for {current_key_str}: {found_key[0]}")
            return found_key

        if len(unique_mappings_dict[current_group[-1]]) < 1:
            unique_mappings_dict[current_group[-1]].append(current_key_str)
            logger.debug(f"Using last key part as unique key: {current_group[-1]}")
            return current_group[-1]

        return self.create_unique_key(current_group, current_key_str, unique_mappings_dict)

    def create_unique_key(self, current_group: List[str], current_key_str: str, unique_mappings_dict: Dict[str, List[str]]) -> str:
        """
        Create a unique key for the current data entry if a simple key is not sufficient.

        Args:
            current_group (List[str]): The list of keys in the current path.
            current_key_str (str): The string representation of the current path.
            unique_mappings_dict (Dict[str, List[str]]): A dictionary tracking unique keys.

        Returns:
            str: A unique key for the current data entry.
        """
        logger.debug(f"Creating a new unique key for: {current_key_str}")
        idx = -2
        while idx >= -len(current_group):
            current_data_key_test = '.'.join(current_group[-idx:])
            if current_data_key_test not in unique_mappings_dict:
                unique_mappings_dict[current_data_key_test].append(current_key_str)
                logger.debug(f"Created unique key: {current_data_key_test}")
                return current_data_key_test
            idx -= 1

        idx = 1
        base_key = current_group[-1]
        current_data_key_test = f'{base_key}.{idx}'
        while current_data_key_test in unique_mappings_dict:
            idx += 1
            current_data_key_test = f'{base_key}.{idx}'

        unique_mappings_dict[current_data_key_test].append(current_key_str)
        logger.debug(f"Created unique key with index: {current_data_key_test}")
        return current_data_key_test


import unittest

class TestKeyDiscoverer(unittest.TestCase):
    
    def test_discover_keys(self):
        sample_json = {
            "name": "John",
            "address": {
                "street": "123 Maple Street",
                "city": "Springfield",
                "state": "IL"
            },
            "phones": [
                {"type": "home", "number": "123-456-7890"},
                {"type": "work", "number": "098-765-4321"}
            ]
        }
        
        expected_keys = {
            'name': ['name'],
            'address': ['address'],
            'street': ['address.street'],
            'city': ['address.city'],
            'state': ['address.state'],
            'phones': ['phones'],
            'type': ['phones.0.type', 'phones.1.type'],
            'number': ['phones.0.number', 'phones.1.number']
        }


        key_discoverer = KeyDiscoverer([sample_json])
        discovered_keys = key_discoverer.get_all_keys()
        #(expected_keys==discovered_keys)
        self.assertEqual(discovered_keys, expected_keys)

import unittest
class TestDynamicDictProcessor(unittest.TestCase):
    
    def test_flatten_json(self):
        sample_json = {
            "name": "John",
            "address": {
                "street": "123 Maple Street",
                "city": "Springfield",
                "state": "IL"
            },
            "phones": [
                {"type": "home", "number": "123-456-7890"},
                {"type": "work", "number": "098-765-4321"}
            ]
        }

        expected_flattened = {
            'name': 'John',
            'street': '123 Maple Street',
            'city': 'Springfield',
            'state': 'IL',
            'type': ['home','work'],
            'number': ['123-456-7890','098-765-4321'],
        }

        processor = DynamicDictProcessor(sample_json)
        flattened_json = processor.process_dictionary().flatten()
        #[obj_info['path'] for obj_info in processor.json_extracted]
        self.assertEqual(flattened_json, expected_flattened)
        
    def test_combine_normalized(self):
        sample_json = {
            "name": "John",
            "bio": ["Developer", "Pythonista", "OpenAI enthusiast"]
        }

        processor = DynamicDictProcessor(sample_json, delimiter=None,obj_delimiter='; ')
        flattened_json = processor.process_dictionary().flatten()
        
        expected_flattened = {
            'name': 'John',
            'bio': 'Developer; Pythonista; OpenAI enthusiast'
        }
        
        self.assertEqual(flattened_json, expected_flattened)



import unittest
class KeyFilterTests(unittest.TestCase):
    def setUp(self):
        # Create a sample dictionary for testing
        self.discovered_keys = {
            "John Doe": ["user.profile.name"],
            "johndoe@example.com": ["user.profile.email"],
            "en-US": ["system.settings.language"],
            "access_log_20240707.txt": ["system.logs.access"],
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        }

    def test_filter_by_prefix(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, prefix="John")
        self.assertEqual(filtered, {
            "John Doe": ["user.profile.name"]
        })

    def test_filter_by_min_length(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, min_length=3)
        self.assertEqual(filtered, {
            "John Doe": ["user.profile.name"],
            "johndoe@example.com": ["user.profile.email"],
            "en-US": ["system.settings.language"],
            "access_log_20240707.txt": ["system.logs.access"],
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_by_substring(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, substring="catalog")
        self.assertEqual(filtered, {
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_by_pattern(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, pattern=r"[a-z]+\d+")  # Match prices
        self.assertEqual(filtered, {
            'Widget X': ['product.catalog.item123.name'],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_with_multiple_criteria(self):
        filtered = KeyFilter.filter_keys(
            self.discovered_keys, substring="product.catalog.item123", min_length=4, prefix="19"
        )
        self.assertEqual(filtered, {
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_with_include_false(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, substring="product", include_matches=False)
        self.assertEqual(filtered, {
            "John Doe": ["user.profile.name"],
            "johndoe@example.com": ["user.profile.email"],
            "en-US": ["system.settings.language"],
            "access_log_20240707.txt": ["system.logs.access"]
        })

if __name__ == '__main__':
    unittest.main(argv=[''], verbosity=2, exit=False)

