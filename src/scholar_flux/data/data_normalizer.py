from typing import Dict, List, Any, Optional
import itertools

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
        path_str = "_".join(map(str, level_names))
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
    def group_path_assignments(path: List[Any]) -> Optional[str]:
        """
        Group the path assignments into a single string, excluding indices.
        
        Args:
            path (List[Any]): The original path containing both keys and indices.
        
        Returns:
            Optional[str]: A single string representing the grouped path, or None if the path is empty.
        """
        logger.debug(f"Grouping path assignments for path: {path}")
        key_path = PathUtils.remove_path_indices(path)
        if key_path:
            grouped_path = " ".join(key_path)
            logger.debug(f"Grouped path: {grouped_path}")
            return grouped_path
        logger.debug("No valid keys found in path")
        return None
    
class DynamicDictProcessor:
    def __init__(self, json_dict: Dict, delimiter: Optional[str] = None, obj_delimiter: str= "; "):
        """
        Initialize the JsonDictParser with a JSON dictionary and a delimiter for joining list elements.

        Args:
            json_dict (Dict): The input JSON dictionary to be parsed.
            delimiter (str): The delimiter used to join elements across multiple keys when normalizing. Default is "\n\n".
            obj_delimiter (str): The delimiter used to join elements max depth list objects. Default is "; ".
        """
        self.json_dict = json_dict
        self.json_extracted = []
        self.paths = []
        self.delimiter = delimiter
        self.obj_delimiter = obj_delimiter
        
    def combine_normalized(self,normalized_field_value:Optional[List]):
        if self.delimiter is not None and isinstance(normalized_field_value,list):
            return self.delimiter.join(normalized_field_value) 
        return normalized_field_value
            

    def flatten(self) -> Optional[Dict[str, List[Any]]]:
        """
        Flatten the nested JSON dictionary into a simpler structure.

        Returns:
            Optional[Dict[str, List[Any]]]: A dictionary with flattened paths as keys and lists of values.
        """
        logger.info("Starting flattening process")
        self.paths.clear()
        self.json_extracted.clear()
        self.process_level(self.json_dict)
        if self.json_extracted:
            logger.info("Normalization process started")
            normalizer = JsonNormalizer(self.json_extracted, self.delimiter)
            normalized_json=normalizer.normalize_extracted()
            normalized_json={data_key:self.combine_normalized(field_value)
                                for data_key,field_value in normalized_json.items()}
            return normalized_json
            
        logger.info("No data extracted, returning None")
        return None

    def process_level(self, obj: Any, level_name: Optional[List[Any]] = None) -> List[Any]:
        """
        Recursively process each level of the JSON dictionary to extract data and paths.

        Args:
            obj (Any): The current level of the JSON object being processed.
            level_name (Optional[List[Any]]): The current path in the JSON object.

        Returns:
            List[Any]: A list of processed levels.
        """
        level_name = level_name if level_name is not None else []
        if isinstance(obj, list):
            logger.debug(f"Processing list at path: {level_name}")
            if any(isinstance(v_i, (list, dict)) for v_i in obj):
                return [self.process_level(v_i, level_name + [i]) for i, v_i in enumerate(obj)]
            joined_obj = self.obj_delimiter.join(map(str, obj))
            return self.process_level(joined_obj, level_name)
        elif isinstance(obj, dict):
            logger.debug(f"Processing dictionary at path: {level_name}")
            return [self.process_level(v, level_name + [k]) for k, v in obj.items()]
        else:
            fmt_name = PathUtils.path_name(level_name)
            obj_info = {'data': obj, 'path': level_name, 'last_key': fmt_name}
            self.json_extracted.append(obj_info)
            logger.debug(f"Extracted data: {obj_info}")
            return [obj_info]


class JsonNormalizer:
    def __init__(self, json_extracted: List[Dict[str, Any]], delimiter: str):
        """
        Initialize the JsonNormalizer with extracted JSON data and a delimiter.

        Args:
            json_extracted (List[Dict[str, Any]]): The list of extracted JSON data.
            delimiter (str): The delimiter used to join elements in lists.
        """
        self.json_extracted = json_extracted
        self.delimiter = delimiter

    def normalize_extracted(self) -> Dict[str, List[Any]]:
        """
        Normalize the extracted JSON data into a flattened dictionary.

        Returns:
            Dict[str, List[Any]]: A dictionary with flattened paths as keys and lists of values.
        """
        logger.info("Starting normalization process")
        flattened_json_dict = defaultdict(list)
        unique_mappings_dict = defaultdict(list)

        for obj_json in self.json_extracted:
            current_path = obj_json['path']
            current_obj = obj_json['data']
            current_group = PathUtils.remove_path_indices(current_path)
            current_key_str = '.'.join(current_group) if current_group else None

            if not current_group:
                logger.debug(f"Skipping empty group for path: {current_path}")
                continue

            current_data_key = self.get_unique_key(current_key_str, current_group, unique_mappings_dict)
            flattened_json_dict[current_data_key].append(current_obj)
            logger.debug(f"Added data to key {current_data_key}: {current_obj}")

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
        found_key = [data_key for data_key, key_str in unique_mappings_dict.items() if current_key_str in key_str]

        if found_key:
            logger.debug(f"Found existing key for {current_key_str}: {found_key[0]}")
            return found_key[0]

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

