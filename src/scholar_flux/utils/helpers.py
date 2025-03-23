import re
import json
import hashlib
import requests
from typing import Any, Dict, List, Optional, Union

import logging
logger = logging.getLogger(__name__)

def flatten(current_data: Optional[Dict|List]) -> Optional[Dict|List]:
    """
    Flattens a dictionary or list if it contains a single element that is a dictionary.

    Args:
        current_data: A dictionary or list to be flattened if it contains a single dictionary element.

    Returns:
        Optional[Dict|List]: The flattened dictionary if the input meets the flattening condition, otherwise returns the input unchanged.
    """
    if isinstance(current_data, list) and len(current_data) == 1 and isinstance(current_data[0], dict):
        return current_data[0]
    return current_data

from typing import Any, Dict, List


def pattern_search(json_dict: Dict,key_to_find: str):
    """
    Searches for keys matching the regex pattern in the given dictionary.

    Args:
        obj: The dictionary to search.
        key_to_find: The regex pattern to search for.

    Returns:
        A list of keys matching the pattern.
    """
    pattern = re.compile(f'{key_to_find}')
    filtered_values = [current_key for current_key in json_dict if pattern.fullmatch(current_key)]
    return filtered_values

def nested_key_exists(obj: Any, key_to_find: str,regex: bool = False) -> bool:
    """
    Recursively checks if a specified key is present anywhere in a given JSON-like dictionary or list structure.

    Args:
        obj: The dictionary or list to search.
        key_to_find: The key to search for.

    Returns:
        True if the key is present, False otherwise.
    """
    if isinstance(obj, dict):
        match=[]

        if regex:
            match = pattern_search(obj,key_to_find) or None

        elif key_to_find in obj:
            match = [key_to_find]

        if match:
            keytype = 'pattern' if regex == True else 'key'
            logger.debug(f'Found match for {keytype}: {key_to_find}; Fields: {match}')
            return True
        for key, value in obj.items():
            if nested_key_exists(value, key_to_find, regex):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if nested_key_exists(item, key_to_find, regex):
                return True
    return False

def get_nested_data(data_dict: Dict[Any, Any], path: List[Any]) -> Optional[Any]:
    """
    Recursively retrieves data from a nested dictionary using a sequence of keys.
    
    Args:
        data_dict (Dict[Any, Any]): The dictionary from which to extract data.
        path (List[Any]): A list of keys representing the path to the desired data within `data_dict`.
    
    Returns:
        Optional[Any]: The value retrieved from the nested dictionary following the path, or None if any key in the path is not found or leads to a None value prematurely.
    """
    current_data = data_dict
    for idx, key in enumerate(path):
        try:
            current_data = current_data[key]
            if idx != len(path) - 1 and not isinstance(path[idx+1],int):
                current_data=flatten(current_data)
        except (KeyError, IndexError, TypeError) as e:
            logger.debug(f"key not found: {str(e)}")
            return None
    return current_data


def recursively_get_nested_data(data_dict: Dict[Any, Any], path: List[Any]) -> Optional[Any]:
    """
    Recursively gets data from a nested dictionary using a list of keys.
    
    Args:
        data_dict (dict): The dictionary from which to extract the value.
        path (list): A list of keys representing the path to the desired value.
    
    Returns:
        The value from the nested dictionary or None if any key is not found.
    """
    if not path:
        logger.debug("Empty path provided, returning the entire data dictionary.")
        return data_dict

    next_key = path[0]
    if next_key not in data_dict:
        logger.warning("Key '%s' not found in the data dictionary: %s", next_key, data_dict.keys())
        return None
    
    next_value = data_dict.get(next_key)
    if next_value is None:
    
        logger.warning(f"Value for Key '%s' found in the data dictionary is NoneType.",next_key)
        return next_value

    if len(path) == 1:
        return next_value

    logger.debug("Traversing nested data for key '%s'.", next_key)
    return get_nested_data(next_value, path[1:])

def generate_response_hash(response: requests.Response):
    # Extract URL directly from the response object
    url = response.url
    
    # Filter for relevant headers directly from the response object
    relevant_headers = {k: v for k, v in response.headers.items() if k in ['ETag', 'Last-Modified']}
    headers_string = str(sorted(relevant_headers.items()))
    
    # Assume response.content is the way to access the raw byte content
    # Check if response.content is not None or empty before hashing
    content_hash = hashlib.sha256(response.content).hexdigest() if response.content else ''
    
    # Combine URL, headers, and content hash into a final cache key
    return hashlib.sha256(f"{url}{headers_string}{content_hash}".encode()).hexdigest()

def compare_response_hashes(response1,response2):
    hash1=generate_response_hash(response1)
    hash2=generate_response_hash(response2)

    return(hash1 is not None and hash2 is not None and hash1 == hash2)

def coerce_int(value: Optional[str]):
    """Attempts to convert a value to an integer, returning None if the conversion fails."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def try_int(value: Optional[str]):
    """Attempts to convert a value to an integer, returning the original value if the conversion fails."""
    converted_value =  coerce_int(value)
    return converted_value or value
    


def as_list_1d(value):
    """
    Summary:
    Converts a value to a one-dimensional list if it is not already a list.

    Explanation:
    This static method takes a value and returns it as a one-dimensional list if the value is not already a list.

    Args:
    - value: The value to be converted to a one-dimensional list.

    Returns:
    - list: The value as a one-dimensional list if it was not already a list.
    """
    if value:
        return value if isinstance(value,list) else [value]

def path_search(obj: Union[Dict, List],key_to_find: str):
    """
    Searches for keys matching the regex pattern in the given dictionary.

    Args:
        obj: The dictionary to search.
        key_to_find: The regex pattern to search for.

    Returns:
        A list of keys matching the pattern.
    """
    pattern = re.compile(f'{key_to_find}')
    filtered_values = [current_key for current_key in obj if pattern.fullmatch(current_key)]
    return filtered_values
### Example usage
#json_data = {
#    "name": "John",
#    "age": 30,
#    "address": {
#        "street": "123 Main St",
#        "city": "Anytown"
#    },
#    "contacts": [
#        {"type": "email", "value": "john@example.com"},
#        {"type": "phone", "value": "123-456-7890"}
#    ]
#}

## Search for a key without regex
#print(nested_key_exists(json_data, "city"))  # Output: ['address', 'city']

## Search for a key with regex
#print(nested_key_search(json_data, "ci.*", regex=True))  # Output: ['address', 'city']
