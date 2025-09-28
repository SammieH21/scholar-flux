import re
import hashlib
import requests
from datetime import datetime, timezone

from typing import (
    Any,
    Dict,
    List,
    Tuple,
    Set,
    Optional,
    Union,
    TypeVar,
    Hashable,
    Callable,
)
from collections.abc import Iterable
import logging

logger = logging.getLogger(__name__)

JSON_TYPE = TypeVar("JSON_TYPE", bound=list | dict | str | int | None)
T = TypeVar("T", bound=Hashable)


def quote_if_string(value: Any) -> Any:
    """
    Attempt to quote string values to distinguish them from object text in class representations.
    Args:
        value (Any): a value that is quoted only if it is a string
    Returns:
        Any: Returns a quoted string if successful. Otherwise returns the value unchanged
    """
    if isinstance(value, str):
        return f"'{value}'"
    return value


def try_quote_numeric(value: Any) -> Optional[str]:
    """
    Attempt to quote numeric values to distinguish them from string values and integers.
    Args:
        value (Any): a value that is quoted only if it is a numeric string or an integer
    Returns:
        Optional[str]: Returns a quoted string if successful. Otherwise None
    """
    if (isinstance(value, str) and value.isdigit()) or isinstance(value, int):
        return f"'{value}'"
    return None


def quote_numeric(value: Any) -> str:
    """
    Attempts to quote as a numeric value and returns the original value if successful
    Otherwise returns the original element
    Args:
        value (Any): a value that is quoted only if it is a numeric string or an integer
    Returns:
        Returns a quoted string if successful.
    Raises:
        ValueError: If the value cannot be quoted

    """
    quoted_value = try_quote_numeric(value)
    if quoted_value is None:
        raise ValueError("The value, ({value}) could not be quoted as numeric string or an integer")
    return quoted_value


def flatten(current_data: Optional[Dict | List]) -> Optional[Dict | List]:
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


def as_tuple(obj: Any) -> tuple:
    """
    Convert or nest an object into a tuple if possible to make available for later function calls
    that require tuples instead of lists, NoneTypes, and other data types.

    Args:
        obj (Any) The object to nest as a tuple
    Returns:

    """
    match obj:
        case tuple():
            return obj
        case list():
            return tuple(obj)
        case set():
            return tuple(obj)
        case None:
            return tuple()
        case _:
            return (obj,)


def pattern_search(json_dict: Dict, key_to_find: str, regex: bool = True) -> List:
    """
    Searches for keys matching the regex pattern in the given dictionary.

    Args:
        obj: The dictionary to search.
        key_to_find: The regex pattern to search for.
        regex: Whether or not to search with regular expressions.

    Returns:
        A list of keys matching the pattern.
    """
    if regex:
        pattern = re.compile(f"{key_to_find}")
        filtered_values = [current_key for current_key in json_dict if pattern.fullmatch(current_key)]
    else:
        filtered_values = [current_key for current_key in json_dict if key_to_find in current_key]
    return filtered_values


def nested_key_exists(obj: Any, key_to_find: str, regex: bool = False) -> bool:
    """
    Recursively checks if a specified key is present anywhere in a given JSON-like dictionary or list structure.

    Args:
        obj: The dictionary or list to search.
        key_to_find: The key to search for.
        regex: Whether or not to search with regular expressions.

    Returns:
        True if the key is present, False otherwise.
    """
    if isinstance(obj, dict):
        match: Optional[List] = []

        if regex:
            match = pattern_search(obj, key_to_find) or None

        elif key_to_find in obj:
            match = [key_to_find]

        if match:
            key_type = "pattern" if regex is True else "key"
            logger.debug(f"Found match for {key_type}: {key_to_find}; Fields: {match}")
            return True
        for value in obj.values():
            if nested_key_exists(value, key_to_find, regex):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if nested_key_exists(item, key_to_find, regex):
                return True
    return False


def get_nested_dictionary_data(data: Dict[str, Any], path: List[str]) -> Any:
    """
    Retrieve data from a nested dictionary using a list of keys as the path.
    """
    for key in path:
        data = data.get(key, {})
        if not isinstance(data, dict):
            break
    return data


def get_nested_data(json: list | dict | None, path: list) -> list | dict | None | str | int:
    """
    Recursively retrieves data from a nested dictionary using a sequence of keys.

    Args:
        json (List[Dict[Any, Any]] | Dict[Any, Any]): The parsed json structure from which to extract data.
        path (List[Any]): A list of keys representing the path to the desired data within `json`.

    Returns:
        Optional[Any]: The value retrieved from the nested dictionary following the path, or None if any
                       key in the path is not found or leads to a None value prematurely.
    """
    current_data = json
    for idx, key in enumerate(path):
        try:
            if current_data:
                current_data = current_data[key]
                if idx != len(path) - 1 and not isinstance(path[idx + 1], int):
                    current_data = flatten(current_data)
        except (KeyError, IndexError, TypeError) as e:
            logger.debug(f"key not found: {str(e)}")
            return None
    return current_data


def generate_response_hash(response: requests.Response) -> str:
    """
    Generates a response hash from a response from requests.
    This function returns a unique identifier for the response
    """
    # Extract URL directly from the response object
    url = response.url

    # Filter for relevant headers directly from the response object
    relevant_headers = {k: v for k, v in response.headers.items() if k in ["ETag", "Last-Modified"]}
    headers_string = str(sorted(relevant_headers.items()))

    # Assume response.content is the way to access the raw byte content
    # Check if response.content is not None or empty before hashing
    content_hash = hashlib.sha256(response.content).hexdigest() if response.content else ""

    # Combine URL, headers, and content hash into a final cache key
    return hashlib.sha256(f"{url}{headers_string}{content_hash}".encode()).hexdigest()


def compare_response_hashes(response1: requests.Response, response2: requests.Response) -> bool:
    """
    Determines whether two responses differ.
    This function uses hashing to generate an identifier unique key_to_find
    the content of the response for comparison purpose later dealing with cache
    """
    hash1 = generate_response_hash(response1)
    hash2 = generate_response_hash(response2)

    return hash1 is not None and hash2 is not None and hash1 == hash2


def coerce_int(value: Any) -> int | None:
    """Attempts to convert a value to an integer, returning None if the conversion fails."""
    try:
        return int(value) if isinstance(value, str) else None
    except (ValueError, TypeError):
        return None


def try_int(value: JSON_TYPE | None) -> JSON_TYPE | int | None:
    """
    Attempts to convert a value to an integer, returning the original value if the conversion fails.
    Args:
        value (Hashable): the value to attempt to coerce into an integer
    Returns:
        Optional[int]:
    """
    converted_value = coerce_int(value)
    return converted_value or value


def try_pop(s: Set[T], item: T, default: Optional[T] = None) -> T | None:
    """
    Attempt to remove an item from a set and return the item if it exists.

    Args:
        item (Hashable): The item to try to remove from the set
        default (Optional[Hashable]): The object to return as a default if `item` is not found

    Returns:
        Optional[Hashable] `item` if the value is in the set, otherwise returns the specified default

    """
    try:
        s.remove(item)
        return item
    except KeyError:
        return default


def try_dict(value: List[Dict] | Dict) -> Optional[Dict]:
    """
    Attempts to convert a value into a dictionary, if possible
    If it is not possible to convert the value into a dictionary,
    the function will return None.
    Args:
        value (List[Dict | Dict): The value to attempt to convert into a dict
    Returns;
        Optional[Dict]: The value converted into a dictionary if possible, otherwise None
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return dict(enumerate(value))
    try:
        return dict(value)
    except (TypeError, ValueError):
        return None


def is_nested(obj: Any) -> bool:
    """
    Indicates whether the current value is  a nested object:
       useful for recursive iterations such as JSON record data.

    Args:
        obj: any (realistic JSON) data type - dicts, lists, strs, numbers
    Returns:
        bool: True if nested otherwise False
    """
    return isinstance(obj, Iterable) and not isinstance(obj, str)


def unlist_1d(current_data: Tuple | List) -> Any:
    """
    Retrieves an element from a list/tuple if it contains only a single element.
    Otherwise, it will return the element as is. Useful for extracting
    text from a single element list/tuple


    Args:
        current_data (Tuple | List): An object potentially unlist if it contains a single element.

    Returns:
        Optional[Any]: The unlisted object if it comes from a single element list/tuple,
                             otherwise returns the input unchanged.
    """
    if isinstance(current_data, (tuple, list)) and len(current_data) == 1:
        return current_data[0]
    return current_data


def as_list_1d(value: Any) -> List:
    """
    Nests a value into a single element list if the value is not already a list.
    Args:
        value (Any): The value to add to a list if it is not already a list
    Returns:
        List: If already a list, the value is returned as is.
              Otherwise, the value is nested in a list.
              Caveat: if the value is None, an empty list is returned
    """
    if value is not None:
        return value if isinstance(value, list) else [value]
    return []


def path_search(obj: Union[Dict, List], key_to_find: str):
    """
    Searches for keys matching the regex pattern in the given dictionary.

    Args:
        obj: The dictionary to search.
        key_to_find: The regex pattern to search for.

    Returns:
        A list of keys matching the pattern.
    """
    pattern = re.compile(f"{key_to_find}")
    filtered_values = [current_key for current_key in obj if pattern.fullmatch(current_key)]
    return filtered_values


def try_call(
    func: Callable,
    args: Optional[tuple] = None,
    kwargs: Optional[dict] = None,
    suppress: tuple = (),
    logger: Optional[logging.Logger] = None,
    log_level: int = logging.WARNING,
    default: Optional[Any] = None,
) -> Optional[Any]:
    """
    A helper function for calling another function safely in the event that
    one of the specified errors occur and are contained within the list of
    errors to suppress.

    Args:
        func: The function to call
        args: A tuple of positional arguments to add to the function call
        kwargs: A dictionary of keyword arguments to add to the function call
        suppress: A tuple of exceptions to handle and suppress if they occur
        logger: The logger to use for warning generation
        default: The value to return in the event that an error occurs and is suppressed
    Returns:
        Optional[Any]: When successful, the return type of the callable is also
        returned without modification. Upon a suppressed exception,
        the function will generate a warning and return `None` by default unless
        default is set
    """

    suppress = as_tuple(suppress)
    args = as_tuple(args)

    received_function = callable(func)

    try:
        if not received_function:
            raise TypeError(f"The current value must be a function. Received type({func})")

        kwargs = kwargs or {}
        return func(*args, **kwargs)
    except suppress as e:
        function_name = getattr(func, "__name__", repr(func))
        if logger:
            logger.log(
                log_level or logging.WARNING,
                f"An error occurred in the call to the function argument, '{function_name}', args={args}, kwargs={kwargs}: {e}",
            )
    return default


def generate_iso_timestamp() -> str:
    """
    Generates and formats an ISO 8601 timestamp string in UTC with millisecond precision
    for reliable round-trip conversion.

    Returns:
        str: ISO 8601 formatted timestamp (e.g., "2024-03-15T14:30:00.123Z")
    """
    return format_iso_timestamp(datetime.now(timezone.utc))


def format_iso_timestamp(timestamp: datetime) -> str:
    """
    Formats an iso timestamp string in UTC with millisecond precision.

    Returns:
        str: ISO 8601 formatted timestamp (e.g., "2024-03-15T14:30:00.123Z")
    """
    return timestamp.isoformat(timespec="milliseconds")


def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Attempts to convert an ISO 8601 timestamp string back to a datetime object.

    Args:
        timestamp_str: ISO 8601 formatted timestamp string

    Returns:
        datetime: datetime object if parsing succeeds, None otherwise
    """
    if not isinstance(timestamp_str, str):
        return None

    try:
        cleaned = timestamp_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt
    except (ValueError, AttributeError, TypeError, OSError):
        return None


if __name__ == "__main__":
    timestamp = generate_iso_timestamp()
    parsed_timestamp = parse_iso_timestamp(timestamp)
    assert parsed_timestamp is not None and format_iso_timestamp(parsed_timestamp) == timestamp
