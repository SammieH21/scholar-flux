# /utils/helpers.py
"""The scholar_flux.utils.helpers module contains several helper functions to aid in common data data manipulation
scenarios including character conversions, date-time parsing and formatting, and nesting and unnesting common python
data structures."""
import re
import hashlib
import requests
from datetime import datetime, timezone, date
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.utils.json_processing_utils import PathUtils
from scholar_flux.utils.record_types import RecordType

from typing import (
    Any,
    Set,
    Optional,
    Union,
    TypeVar,
    Hashable,
    Mapping,
    Sequence,
    Callable,
    TYPE_CHECKING,
    Literal,
    overload,
)
from collections.abc import Iterable
import logging

if TYPE_CHECKING:
    from bs4 import BeautifulSoup
else:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

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
V = TypeVar("V", bound=Any)
D = TypeVar("D", bound=Any)


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
    """Attempts to quote as a numeric value and returns the quoted value if successful. Otherwise raises an error.

    Args:
        value (Any): a value that is quoted only if it is a numeric string or an integer

    Returns:
        str: Returns a quoted string if successful.

    Raises:
        ValueError: If the value cannot be quoted

    """
    quoted_value = try_quote_numeric(value)
    if quoted_value is None:
        raise ValueError("The value, ({value}) could not be quoted as numeric string or an integer")
    return quoted_value


def flatten(current_data: Optional[Mapping | list]) -> Optional[Mapping | list]:
    """Flattens a dictionary or list if it contains a single element that is a dictionary.

    Args:
        current_data (Optional[Mapping | list]): A dictionary or list to be flattened if it contains a single dictionary element.

    Returns:
        Optional[Mapping | list]: The flattened dictionary if the input meets the flattening condition, otherwise returns the input unchanged.

    """
    if isinstance(current_data, list) and len(current_data) == 1 and isinstance(current_data[0], dict):
        return current_data[0]
    return current_data


def as_tuple(obj: Any) -> tuple:
    """Converts objects into tuples when possible and nests objects within a tuple otherwise.

    This function is useful as a preprocessing step for function calls that require tuples instead of lists, NoneTypes,
    and other data types.

    Args:
        obj (Any): The object to nest as a tuple

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


def pattern_search(json_dict: dict, key_to_find: str, regex: bool = True) -> list:
    """Searches for keys matching the regex pattern in the given dictionary.

    Args:
        json_dict (dict): The dictionary to search.
        key_to_find (str): The regex pattern to search for.
        regex (bool): Whether or not to search with regular expressions.

    Returns:
        list: A list of keys matching the pattern.

    """
    if regex:
        pattern = re.compile(f"{key_to_find}")
        filtered_values = [current_key for current_key in json_dict if pattern.fullmatch(current_key)]
    else:
        filtered_values = [current_key for current_key in json_dict if key_to_find in current_key]
    return filtered_values


@overload
def infer_text_pattern_search(
    text: str,
    pattern_dict: Mapping[str | re.Pattern, V] | Mapping[str, V] | Mapping[re.Pattern, V],
    default: D,
    *,
    regex: bool = True,
    flags: int | re.RegexFlag = 0,
) -> V | D:
    """Returns a non-None value when no None exists in dictionary values or default."""
    ...


@overload
def infer_text_pattern_search(
    text: str,
    pattern_dict: Mapping[str | re.Pattern, Optional[V]] | Mapping[str, Optional[V]] | Mapping[re.Pattern, V],
    default: None = None,
    *,
    regex: bool = True,
    flags: int | re.RegexFlag = 0,
) -> Optional[V]:
    """When the `default` is None, either an available pattern will be returned, or None is returned instead."""
    ...


def infer_text_pattern_search(
    text: str,
    pattern_dict: Mapping[str | re.Pattern, Optional[V]] | Mapping[str, Optional[V]] | Mapping[re.Pattern, V],
    default: Optional[D] = None,
    *,
    regex: bool = True,
    flags: int | re.RegexFlag = 0,
) -> Optional[V | D]:
    """Infers a category based on a text pattern search. If a value match can't be inferred, a default is returned.

    Args:
        text (str):
            The text to match. If None or missing, the default is returned instead.
        pattern_dict (Mapping[str | re.Pattern, Optional[V]] | Mapping[str, Optional[V]] | Mapping[re.Pattern, V]):
            A dictionary that maps patterns to potential output values provided that the pattern matches.
        default (Optional[D]):
            The value to return if a match cannot be inferred from text pattern matching.
        regex (bool):
            Whether to interpret patterns as regex (default True).
        flags (int | re.RegexFlag):
            Optional flags to pass to `re.search` when available. (default `flags=0` for no flags)

    Returns:
        Optional[V | D]:
            The inferred category when a match is found based on a dictionary mapping, and the default otherwise.


    Note:
        If the provided value is not a mapping or if the provided value cannot be coerced into a string, the default is
        returned instead.

    """
    # Replace empty strings, "Unknown", "None" (string form or NoneType)
    if isinstance(pattern_dict, Mapping) and (cleaned_text := try_none(coerce_str(text))):
        for pattern, inferred_type in pattern_dict.items():
            pattern = (
                re.escape(str(pattern))
                if not regex
                else (pattern if isinstance(pattern, (str, re.Pattern)) else str(pattern))
            )
            if re.search(pattern, cleaned_text, flags=flags):
                return inferred_type
    return default


def nested_key_exists(obj: Any, key_to_find: str, regex: bool = False) -> bool:
    """Recursively checks if a specified key is present anywhere in a given JSON-like dictionary or list structure.

    Args:
        obj (Any): The dictionary or list to search.
        key_to_find (str): The key to search for.
        regex (bool): Whether or not to search with regular expressions.

    Returns:
        bool: True if the key is present, False otherwise.

    """
    if isinstance(obj, dict):
        match: Optional[list] = []

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


def get_nested_dictionary_data(data: Mapping[Any, Any], path: list[str]) -> Any:
    """Retrieve data from a nested dictionary using a list of keys as the path.

    Args:
        data (Mapping[Any, Any]): The nested dictionary to retrieve data from.
        path (list[str]): A list of keys representing the path to the desired data.

    Returns:
        Any: The value retrieved from the nested dictionary following the path.

    """
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
        json (list | Mapping | None): The parsed json structure from which to extract data.
        path (str | list): A list of keys representing the path to the desired data within `json`.
        flatten_nested_dictionaries (bool): Determines whether single-element lists containing dictionary data should be extracted.
        verbose (bool): Determines whether logging should occur when an error is encountered.

    Returns:
        Any: The value retrieved from the nested dictionary following the path, or None if any
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


def filter_record_key_prefixes(
    record: Mapping[str, Any] | Mapping[str | int, Any], prefix: str, invert: bool = False
) -> RecordType:
    """Removes or retains keys from dictionaries and mappings beginning with a specific string prefix.

    Args:
        record (Mapping[str, Any] | Mapping[str | int, Any]):
            A dictionary record to filter keys containing specific prefixes
        prefix (str):
            The prefix to filter from the dictionary. Prefixes that are not strings will be coerced into
            strings internally, but only string-typed fields will be matched.
        invert (bool):
            If False, dictionary keys beginning with the prefix are removed (default behavior). If true,
            fields beginning with the prefix are retained instead.
    Returns:
        JSON_MAPPING: The filtered record after retaining (invert=True) or removing (invert=False) string prefixes.

    """
    if not isinstance(record, Mapping):
        raise TypeError(f"Expected a dictionary record to filter key prefixes from, but received type {type(record)}")

    if not isinstance(prefix, str):
        prefix = str(prefix)

    return {
        field: value
        for field, value in record.items()
        if (not isinstance(field, str) or not field.startswith(prefix)) ^ bool(invert)
    }


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
        response (requests.Response | ResponseProtocol): An http response or response-like object.

    Returns:
        str: A unique identifier for the response.

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
    """Determines whether two responses have identical content.

    This function uses hashing to generate an identifier unique to the content of the response for comparison purposes.

    Args:
        response1 (requests.Response | ResponseProtocol): The first response object.
        response2 (requests.Response | ResponseProtocol): The second response object.

    Returns:
        bool: True if the responses have identical content, False otherwise.

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

    if isinstance(value, re.Pattern):
        return value.pattern

    try:
        return value.decode(encoding or "utf-8") if isinstance(value, bytes) else str(value)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def coerce_flattened_str(
    value: Any,
    delimiter: str = "; ",
) -> Optional[str]:
    """Coerces strings or sequences of strings into a single, flattened string.

    This function handles the common pattern of normalizing journal names, keywords, or
    other metadata that may arrive as either a string or list of strings.
    Sequences of strings are handled by joining them, and if a sequence cannot be converted
    to a sequence of strings, None is returned instead.

    Args:
        value (Any): A string, bytes, list/tuple of strings, or None
        delimiter (str): The string used to join list elements with (default: "; ")

    Returns:
        Optional[str]: A single string (coerced or joined), or None if conversion fails

    """
    # Return strings early
    if isinstance(value, str):
        return value or None

    # Filter out sequences
    if not isinstance(value, Sequence):
        return None

    # Filter out any None values and empty strings
    nested_entries = [nested_entry for nested_entry in value if nested_entry]

    # Return a string only if each entry in the sequence/tuple is a string.
    return (
        delimiter.join(nested_entries)
        if all(isinstance(nested_entry, str) for nested_entry in nested_entries)
        else None
    )


def try_none(value: Any, none_indicators: tuple[Any, ...] = ("none", "unspecified", "unknown")) -> Any:
    """Converts empty strings, 'none', and empty data containers into None. Otherwise, the original value is returned.

    Args:
        value (Any): The value to convert into None when possible
        none_indicators (tuple[Any, ...]): Tuple of values that should be treated as None indicators.

    Returns:
        Any: The original value if not converted, and None otherwise

    """

    formatted_value = value.strip().lower() if isinstance(value, str) else value
    none_indicators = as_tuple(none_indicators)
    return value if (formatted_value or isinstance(value, int)) and formatted_value not in none_indicators else None


def try_int(value: JSON_ELEMENT_TYPE | Any) -> JSON_ELEMENT_TYPE | int | Any:
    """Attempts to convert a value to an integer, returning the original value if the conversion fails.

    Args:
        value (JSON_ELEMENT_TYPE | None): the value to attempt to coerce into an integer

    Returns:
        JSON_ELEMENT_TYPE | int | Any: The converted integer if successful, otherwise the original value.

    """
    converted_value = coerce_int(value)
    return converted_value if isinstance(converted_value, int) else value


def try_str(value: Any) -> str | Any:
    """Attempts to convert a value to a string, returning the original value if the conversion fails.

    Args:
        value (Any): the value to attempt to coerce into an string

    Returns:
        str | Any: The converted string if successful, otherwise the original value.

    """
    converted_value = coerce_str(value)
    return converted_value if isinstance(converted_value, str) else value


def try_pop(s: Set[T], item: T, default: Optional[T] = None) -> T | None:
    """Attempt to remove an item from a set and return the item if it exists.

    Args:
        s (Set[T]): The set to remove the item from.
        item (T): The item to try to remove from the set
        default (Optional[T]): The object to return as a default if `item` is not found

    Returns:
        T | None: `item` if the value is in the set, otherwise returns the specified default

    """
    try:
        s.remove(item)
        return item
    except KeyError:
        return default


def try_dict(value: list | tuple | dict) -> Optional[dict]:
    """Attempts to convert a value into a dictionary, if possible. If it is not possible to convert the value into a
    dictionary, the function will return None.

    Args:
        value (list | tuple | dict): The value to attempt to convert into a dict

    Returns:
        Optional[dict]: The value converted into a dictionary if possible, otherwise None

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
    """Automatically retrieves `.values()` from dictionaries when available and returns the original input otherwise.

    Args:
        obj (Iterable): An object to get the values from.

    Returns:
        Iterable: An iterable created from `obj.values()` if the object is a dictionary and the original object otherwise.
                  If the object is empty or is not a nested object, an empty list is returned.

    """
    if not is_nested(obj):
        return []
    return obj.values() if isinstance(obj, Mapping) else obj


def is_nested_json(obj: Any) -> bool:
    """Check if a value is a nested, parsed JSON structure.

    Args:
        obj (Any): The object to check.

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


def unlist_1d(current_data: tuple | list | Any) -> Any:
    """Retrieves an element from a list/tuple if it contains only a single element. Otherwise, it will return the
    element as is. Useful for extracting text from a single element list/tuple.

    Args:
        current_data (tuple | list | Any): An object potentially unlist if it contains a single element.

    Returns:
        Any: The unlisted object if it comes from a single element list/tuple,
             otherwise returns the input unchanged.

    """
    if isinstance(current_data, (tuple, list)) and len(current_data) == 1:
        return current_data[0]
    return current_data


def as_list_1d(value: Any) -> list:
    """Nests a value into a single element list if the value is not already a list.

    Args:
        value (Any): The value to add to a list if it is not already a list

    Returns:
        list:
            If already a list, the value is returned as is. Otherwise, the value is nested in a list.
            Caveat: if the value is None, an empty list is returned

    """
    if value is not None:
        return value if isinstance(value, list) else [value]
    return []


def path_search(obj: Union[dict, list], key_to_find: str) -> list[str]:
    """Searches for keys matching the regex pattern in the given dictionary. This function only verifies top-level keys
    rather than nested values.

    Args:
        obj (Union[dict, list]): The dictionary to search.
        key_to_find (str): The regex pattern to search for.

    Returns:
        list[str]: A list of keys matching the pattern.

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
        func (Callable): The function to call
        args (Optional[tuple]): A tuple of positional arguments to add to the function call
        kwargs (Optional[dict]): A dictionary of keyword arguments to add to the function call
        suppress (tuple): A tuple of exceptions to handle and suppress if they occur
        logger (Optional[logging.Logger]): The logger to use for warning generation
        log_level (int): The logging level to use when logging suppressed exceptions.
        default (Optional[Any]): The value to return in the event that an error occurs and is suppressed

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

    Args:
        timestamp (datetime): The datetime object to format.

    Returns:
        str: ISO 8601 formatted timestamp (e.g., "2024-03-15T14:30:00.123Z")

    """
    return timestamp.isoformat(timespec="milliseconds")


def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Attempts to convert an ISO 8601 timestamp string back to a datetime object.

    Args:
        timestamp_str (str): ISO 8601 formatted timestamp string

    Returns:
        Optional[datetime]: datetime object if parsing succeeds, None otherwise

    """
    if not isinstance(timestamp_str, str):
        return None

    try:
        cleaned = timestamp_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt
    except (ValueError, AttributeError, TypeError, OSError):
        return None


def extract_year(value: Any, format: str = "%Y-%m-%d") -> Optional[int]:
    """Extract a 4-digit year from a date string.

    Attempts to parse the value using the specified format, then falls back to regex extraction.

    Args:
        value (Any): A value (generally a string or integer) potentially containing a year.
        format: The expected date format (strptime format string). Defaults to "%Y-%m-%d".

    Returns:
        The extracted year as an integer, or None if extraction fails.

    Examples:
        >>> from datetime import date
        >>> from scholar_flux.utils.helpers import extract_year
        >>> extract_year(date(2027,5, 5))
        # OUTPUT: 2027
        >>> extract_year("2026-03-01")
        # OUTPUT: 2026
        >>> extract_year("03/15/2024", format="%m/%d/%Y")
        # OUTPUT: 2024
        >>> extract_year("2023")
        # OUTPUT: 2023
        >>> extract_year(None)
        # OUTPUT: None

    """
    if (year_number := coerce_int(value)) and 1900 < year_number < 2100:
        return year_number

    if not isinstance(value, (str, date, datetime)):
        return None

    # Directly extracts year from datetime and dates
    if isinstance(value, (date, datetime)):
        return value.year

    # Try parsing with specified format
    try:
        return datetime.strptime(value, format).year
    except ValueError:
        pass

    # Fall back to regex for embedded years or year-only strings
    match = re.search(r"\b\d{4}\b", value)
    if match:
        year_number = coerce_int(match.group())
        return year_number if year_number and 1900 < year_number < 2100 else None

    return None


def convert_month_as_integer(month_str: Optional[str]) -> Optional[str]:
    """Convert month name or number to zero-padded number.

    Args:
        month_str: Month as name ('Dec', 'January') or number ('12', '1')

    Returns:
        Zero-padded month number ('01'-'12') or None if invalid

    Examples:
        >>> convert_month_as_integer('Dec')
        # OUTPUT: '12'
        >>> convert_month_as_integer('1')
        # OUTPUT: '01'
        >>> convert_month_as_integer('January')
        # OUTPUT: '01'
        >>> convert_month_as_integer('')
        # OUTPUT: None

    """
    month_map = {
        "jan": "01",
        "feb": "02",
        "mar": "03",
        "apr": "04",
        "may": "05",
        "jun": "06",
        "jul": "07",
        "aug": "08",
        "sep": "09",
        "oct": "10",
        "nov": "11",
        "dec": "12",
    }
    if not month_str:
        return None
    # If already numeric, zero-pad
    if month_str.isdigit() and 1 <= int(month_str) <= 12:
        return month_str.zfill(2)
    # Convert name to number
    return month_map.get(month_str.lower()[:3])


def build_iso_date(
    year: Optional[str],
    month: Optional[str] = "",
    day: Optional[str] = "",
) -> Optional[str]:
    """Build ISO-formatted date string with graduated precision.

    Constructs date strings in ISO format with appropriate precision based on
    available components. Returns full date (YYYY-MM-DD) if all components present,
    year-month (YYYY-MM) if only year and month available, or year only (YYYY).

    Args:
        year (Optional[str]): Year as string (required for output)
        month (Optional[str]): Month as string (name or number), optional
        day (Optional[str]): Day as string, optional

    Returns:
        Optional[str]: ISO date string with graduated precision (YYYY-MM-DD, YYYY-MM, or YYYY),
                       or None if year is empty/None

    Examples:
        >>> build_iso_date('2025', '12', '19')
        # OUTPUT: '2025-12-19'
        >>> build_iso_date('2025', 'Dec')
        # OUTPUT: '2025-12'
        >>> build_iso_date('2025', 'Dec', '19')
        # OUTPUT: '2025-12-19'
        >>> build_iso_date('2025')
        # OUTPUT: '2025'
        >>> build_iso_date('')
        # OUTPUT: None

    """
    if not coerce_int(year):
        return None

    # Convert month format if converter provided
    month_normalized = convert_month_as_integer(str(month))

    # Extremely basic checks for validated days of the month
    day = (str(day) if 1 <= day_number <= 31 else None) if (day_number := coerce_int(day)) else None

    # Build date string with appropriate precision
    if month_normalized and day:
        return f"{year}-{month_normalized}-{day.zfill(2)}"
    elif month_normalized:
        return f"{year}-{month_normalized}"
    else:
        return str(year)


def strip_html_tags(
    text: str, parser: Literal["html.parser", "lxml"] = "html.parser", verbose: bool = True, **kwargs
) -> str:
    """Extracts the raw text from HTML while removing html elements such as paragraph tags and breaks.

    Args:
        text (str): The text to extract and remove html tags and elements from
        parser (Literal['html.parser', 'lxml']): The parser to use for the removal of html elements
        verbose (bool): Indicates whether issues regarding missing dependencies and incorrect types should be logged.
        **kwargs:
            Additional keyword arguments to be passed directly to `BeautifulSoup.get_text()`. Possible keywords include:
            - separator (str): String inserted between elements (default: '')
            - strip (bool): Whether to strip whitespace from element text (default: False)

    Returns:
        str: The string with text elements removed if the input is a string and the original input otherwise.

    Examples:
        >>> strip_html_tags("<p>Hello</p><p>World</p>")
        'HelloWorld'
        >>> strip_html_tags("<p>Hello</p><p>World</p>", separator=" ")
        'Hello World'
        >>> strip_html_tags("<p>  Whitespace  </p>", strip=True)
        'Whitespace'

    """
    if BeautifulSoup is None:
        if verbose:
            logger.warning("`beautifulsoup4` is not installed. Skipping html tag removal...")
        return text

    return BeautifulSoup(text, parser).get_text(**kwargs) if text and isinstance(text, str) and "<" in text else text


__all__ = [
    "get_nested_data",
    "filter_record_key_prefixes",
    "infer_text_pattern_search",
    "nested_key_exists",
    "get_first_available_key",
    "generate_response_hash",
    "coerce_int",
    "coerce_str",
    "coerce_flattened_str",
    "try_none",
    "try_str",
    "try_int",
    "try_dict",
    "try_pop",
    "try_call",
    "as_list_1d",
    "as_tuple",
    "unlist_1d",
    "is_nested",
    "get_values",
    "is_nested_json",
    "try_quote_numeric",
    "quote_numeric",
    "quote_if_string",
    "extract_year",
    "build_iso_date",
    "generate_iso_timestamp",
    "format_iso_timestamp",
    "parse_iso_timestamp",
    "strip_html_tags",
]
