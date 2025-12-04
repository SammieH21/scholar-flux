# /utils/helpers.py
"""The scholar_flux.utils.helpers module contains several helper functions to aid in common data data manipulation
scenarios including character conversions, date-time parsing and formatting, and nesting and unnesting common python
data structures."""
import re
import hashlib
import requests
from datetime import datetime, timezone
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.utils.json_processing_utils import PathUtils

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
    Mapping,
    Sequence,
    Callable,
)
from collections.abc import Iterable
import logging

logger = logging.getLogger(__name__)

JSON_ELEMENT = dict | list | str | bytes | int | float | bool | None
JSON_VALUE = str | bytes | int | float | bool | None
JSON_MAPPING = dict[str, Any] | dict[str | int, Any]
JSON_SEQUENCE = list[JSON_MAPPING] | list[JSON_VALUE] | list[JSON_MAPPING | JSON_VALUE]

JSON_MAPPING_TYPE = TypeVar("JSON_MAPPING_TYPE", bound=JSON_MAPPING)
JSON_SEQUENCE_TYPE = TypeVar("JSON_SEQUENCE_TYPE", bound=JSON_SEQUENCE)
JSON_ELEMENT_TYPE = TypeVar("JSON_ELEMENT_TYPE", bound=JSON_ELEMENT)
JSON_VALUE_TYPE = TypeVar("JSON_VALUE_TYPE", bound=JSON_VALUE)
JSON_TYPE = TypeVar("JSON_TYPE", JSON_MAPPING, JSON_SEQUENCE)
JSON_DATA_TYPE = TypeVar("JSON_DATA_TYPE", bound=JSON_ELEMENT | JSON_MAPPING | JSON_SEQUENCE)

T = TypeVar("T", bound=Hashable)


def quote_if_string(value: Any) -> Any:
    """Attempt to quote string values to distinguish them from object text in class representations.

    Args:
        value (Any): a value that is quoted only if it is a string

    Returns:
        Any: Returns a quoted string if successful. Otherwise returns the value unchanged

    """
    if isinstance(value, str):
        return f"'{value}'"
    return value


def try_quote_numeric(value: Any) -> Optional[str]:
    """Attempt to quote numeric values to distinguish them from string values and integers.

    Args:
        value (Any): a value that is quoted only if it is a numeric string or an integer

    Returns:
        Optional[str]: Returns a quoted string if successful. Otherwise None

    """
    if (isinstance(value, str) and value.isdigit()) or isinstance(value, int):
        return f"'{value}'"
    return None


def quote_numeric(value: Any) -> str:
    """Attempts to quote as a numeric value and returns the original value if successful Otherwise returns the original
    element.

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


def flatten(current_data: Optional[Mapping | List]) -> Optional[Mapping | List]:
    """Flattens a dictionary or list if it contains a single element that is a dictionary.

    Args:
        current_data: A dictionary or list to be flattened if it contains a single dictionary element.

    Returns:
        Optional[Mapping|List]: The flattened dictionary if the input meets the flattening condition, otherwise returns the input unchanged.

    """
    if isinstance(current_data, list) and len(current_data) == 1 and isinstance(current_data[0], dict):
        return current_data[0]
    return current_data


def as_tuple(obj: Any) -> tuple:
    """Convert or nest an object into a tuple if possible to make available for later function calls that require tuples
    instead of lists, NoneTypes, and other data types.

    Args:
        obj (Any) The object to nest as a tuple

    Returns:
        tuple: The original object converted into a tuple

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
    """Searches for keys matching the regex pattern in the given dictionary.

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
    """Recursively checks if a specified key is present anywhere in a given JSON-like dictionary or list structure.

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


def get_nested_dictionary_data(data: Mapping[Any, Any], path: List[str]) -> Any:
    """Retrieve data from a nested dictionary using a list of keys as the path."""
    for key in path:
        data = data.get(key, {})
        if not isinstance(data, Mapping):
            break
    return data


def get_nested_data(
    json: list | Mapping | None, path: str | list, flatten_nested_dictionaries: bool = True, verbose: bool = True
) -> Any:
    """Recursively retrieves data from a nested dictionary using a sequence of keys.

    Args:
        json (List[Mapping[Any, Any]] | Mapping[Any, Any]): The parsed json structure from which to extract data.
        path (List[Any]): A list of keys representing the path to the desired data within `json`.
        flatten_nested_dictionaries (bool): Determines whether single-element lists containing dictionary data should be extracted.
        verbose (bool): Determines whether logging should occur when an error is encountered.

    Returns:
        Optional[Any]: The value retrieved from the nested dictionary following the path, or None if any
                       key in the path is not found or leads to a None value prematurely.

    """
    current_data = json

    path_list = PathUtils.path_split(path) if isinstance(path, str) else path

    for idx, key in enumerate(path_list):
        try:
            if isinstance(current_data, (dict, list)):
                current_data = current_data[key]
                if (
                    flatten_nested_dictionaries
                    and idx != len(path_list) - 1
                    and not isinstance(path_list[idx + 1], int)
                ):
                    current_data = flatten(current_data)
        except (KeyError, IndexError, TypeError) as e:
            if verbose:
                logger.debug(f"key not found: {str(e)}")
            return None
    return current_data


def get_first_available_key(
    data: Mapping[T | str, Any], keys: Sequence[T | str], default: Any = None, case_sensitive: bool = True
) -> Any:
    """Extracts the first key from a sequence of keys that can be found within a dictionary.

    Args:
        data (Mapping[T | str, Any]): A dictionary or dictionary-like object to extract an existing data element from.
        keys (Sequence[T | str] | Set[T | str]):
            A sequence or set of keys used for the extraction of the first available data element.
        default (Any): The value to use if none of the checked keys are available in the dictionary.
        case_sensitive (bool): Defines whether data element retrieval should rely on case sensitivity (Default=True).

    Returns:
        Any: The value associated with the first available dictionary key

    """
    if not case_sensitive and isinstance(data, Mapping):
        data = {k.lower() if isinstance(k, str) else k: v for k, v in data.items()}
        keys = [k.lower() if isinstance(k, str) else k for k in keys]
    return next((data[key] for key in keys if key in data), default)


def generate_response_hash(response: requests.Response | ResponseProtocol) -> str:
    """Generates a response hash from a response or response-like object that implements the ResponseProtocol.

    Args:
        response (requests.Response | ResponseProtocol):
            An http response or response-like object.
    Returns:
        A unique identifier for the response.

    """
    # Extract URL directly from the response object
    url = response.url

    # Filter for relevant headers directly from the response object
    header_names = {"etag", "last-modified"}
    relevant_headers = {k: v for k, v in response.headers.items() if str(k).lower() in header_names}
    headers_string = str(sorted(f"{str(k).lower()}: {v}" for k, v in relevant_headers.items()))

    # Assume response.content is the way to access the raw byte content
    # Check if response.content is not None or empty before hashing
    content_hash = hashlib.sha256(response.content).hexdigest() if response.content else ""

    # Combine URL, headers, and content hash into a final cache key
    return hashlib.sha256(f"{url}{headers_string}{content_hash}".encode()).hexdigest()


def compare_response_hashes(
    response1: requests.Response | ResponseProtocol, response2: requests.Response | ResponseProtocol
) -> bool:
    """Determines whether two responses differ.

    This function uses hashing to generate an identifier unique key_to_find the content of the response for comparison
    purpose later dealing with cache

    """
    hash1 = generate_response_hash(response1)
    hash2 = generate_response_hash(response2)

    return hash1 is not None and hash2 is not None and hash1 == hash2


def coerce_int(value: Any) -> int | None:
    """Attempts to convert a value to an integer, returning None if the conversion fails.

    Args:
        value (Any): The value to attempt to convert into a int.

    Returns:
        Optional[int]: The value converted into an integer if possible, otherwise None

    """
    if isinstance(value, int) or value is None:
        return value

    try:
        return int(value) if isinstance(value, str) else None
    except (ValueError, TypeError):
        return None


def coerce_str(value: Any, encoding: Optional[str] = "utf-8") -> Optional[str]:
    """Attempts to convert a value into a string, if possible, returning None if conversion fails.

    Args:
        value (Any): The value to attempt to convert into a string.
        encoding (Optional[str]): An optional value used to decode byte strings. Not relevant for data of other types.

    Returns:
        Optional[str]: The value converted into a string if possible, otherwise None

    """
    if isinstance(value, str) or value is None:
        return value

    try:
        return value.decode(encoding or "utf-8") if isinstance(value, bytes) else str(value)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def try_int(value: JSON_ELEMENT_TYPE | None) -> JSON_ELEMENT_TYPE | int | None:
    """Attempts to convert a value to an integer, returning the original value if the conversion fails.

    Args:
        value (JSON_ELEMENT_TYPE): the value to attempt to coerce into an integer

    Returns:
        Optional[JSON_ELEMENT_TYPE| int | None]:

    """
    converted_value = coerce_int(value)
    return converted_value if isinstance(converted_value, int) else value


def try_str(value: Any) -> str | None:
    """Attempts to convert a value to a string, returning the original value if the conversion fails.

    Args:
        value (Any): the value to attempt to coerce into an string

    Returns:
        Optional[str]:

    """
    converted_value = coerce_str(value)
    return converted_value if isinstance(converted_value, str) else value


def try_pop(s: Set[T], item: T, default: Optional[T] = None) -> T | None:
    """Attempt to remove an item from a set and return the item if it exists.

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


def try_dict(value: List | Tuple | Dict) -> Optional[Dict]:
    """Attempts to convert a value into a dictionary, if possible. If it is not possible to convert the value into a
    dictionary, the function will return None.

    Args:
        value (List[Dict | Tuple | Dict): The value to attempt to convert into a dict
    Returns:
        Optional[Dict]: The value converted into a dictionary if possible, otherwise None

    """
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple)):
        return dict(enumerate(value))
    try:
        return dict(value)
    except (TypeError, ValueError):
        return None


def is_nested(obj: Any) -> bool:
    """Indicates whether the current value is a nested object. Useful for recursive iterations such as JSON record data.

    Args:
        obj: any (realistic JSON) data type - dicts, lists, strs, numbers

    Returns:
        bool: True if nested otherwise False

    """
    return isinstance(obj, Iterable) and not isinstance(obj, str)


def get_values(obj: Iterable) -> Iterable:
    """Automatically retrieves values from dictionaries when available and returns the original value if nested.

    Args:
        obj (Iterable): An object to get the values from.

    Returns:
        An iterable created from `obj.values()` if the object is a dictionary and the original object otherwise.
        If the object is empty or is not a nested object, an empty list is returned.

    """
    if not is_nested(obj):
        return []
    return obj.values() if isinstance(obj, Mapping) else obj


def is_nested_json(obj: Any) -> bool:
    """Check if a value is a nested, parsed JSON structure.

    Args:
        record: The record to check.

    Returns:
        bool: False if the value is not a Json-like structure and, True if it is a nested JSON structure.

    """

    if not is_nested(obj) or not obj:
        return False

    # determine whether any keys also contain nested values
    for nested_obj in get_values(obj):
        if isinstance(nested_obj, Mapping):
            return True

        if is_nested(nested_obj):
            for value in nested_obj:
                if is_nested(value):
                    return True
    return False


def unlist_1d(current_data: Tuple | List | Any) -> Any:
    """Retrieves an element from a list/tuple if it contains only a single element. Otherwise, it will return the
    element as is. Useful for extracting text from a single element list/tuple.

    Args:
        current_data (Tuple | List | Any): An object potentially unlist if it contains a single element.

    Returns:
        Optional[Any]:
            The unlisted object if it comes from a single element list/tuple,
            otherwise returns the input unchanged.

    """
    if isinstance(current_data, (tuple, list)) and len(current_data) == 1:
        return current_data[0]
    return current_data


def as_list_1d(value: Any) -> List:
    """Nests a value into a single element list if the value is not already a list.

    Args:
        value (Any): The value to add to a list if it is not already a list

    Returns:
        List:
            If already a list, the value is returned as is. Otherwise, the value is nested in a list.
            Caveat: if the value is None, an empty list is returned

    """
    if value is not None:
        return value if isinstance(value, list) else [value]
    return []


def path_search(obj: Union[Dict, List], key_to_find: str) -> list[str]:
    """Searches for keys matching the regex pattern in the given dictionary. This function only verifies top-level keys
    rather than nested values.

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
    """A helper function for calling another function safely in the event that one of the specified errors occur and are
    contained within the list of errors to suppress.

    Args:
        func: The function to call
        args: A tuple of positional arguments to add to the function call
        kwargs: A dictionary of keyword arguments to add to the function call
        suppress: A tuple of exceptions to handle and suppress if they occur
        logger: The logger to use for warning generation
        default: The value to return in the event that an error occurs and is suppressed

    Returns:
        Optional[Any]:
            When successful, the return type of the callable is also returned without modification. Upon suppressing an exception,
            the function will generate a warning and return `None` by default unless the default was set.

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
    """Generates and formats an ISO 8601 timestamp string in UTC with millisecond precision for reliable round-trip
    conversion.

    Example usage:
        >>> from scholar_flux.utils import generate_iso_timestamp, parse_iso_timestamp, format_iso_timestamp
        >>> timestamp = generate_iso_timestamp()
        >>> parsed_timestamp = parse_iso_timestamp(timestamp)
        >>> assert parsed_timestamp is not None and format_iso_timestamp(parsed_timestamp) == timestamp

    Returns:
        str: ISO 8601 formatted timestamp (e.g., "2024-03-15T14:30:00.123Z")

    """
    return format_iso_timestamp(datetime.now(timezone.utc))


def format_iso_timestamp(timestamp: datetime) -> str:
    """Formats an iso timestamp string in UTC with millisecond precision.

    Returns:
        str: ISO 8601 formatted timestamp (e.g., "2024-03-15T14:30:00.123Z")

    """
    return timestamp.isoformat(timespec="milliseconds")


def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Attempts to convert an ISO 8601 timestamp string back to a datetime object.

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


__all__ = [
    "get_nested_data",
    "nested_key_exists",
    "get_first_available_key",
    "generate_response_hash",
    "coerce_int",
    "coerce_str",
    "try_str",
    "try_int",
    "try_dict",
    "try_pop",
    "try_call",
    "as_list_1d",
    "unlist_1d",
    "is_nested",
    "get_values",
    "is_nested_json",
    "try_quote_numeric",
    "quote_numeric",
    "quote_if_string",
    "generate_iso_timestamp",
    "format_iso_timestamp",
    "parse_iso_timestamp",
]
