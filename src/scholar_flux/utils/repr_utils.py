# /utils/repr_utils.py
"""The scholar_flux.utils.repr_utils module includes several methods used in the creation of descriptive representations
of custom objects such as custom classes, dataclasses, and base models. This module can be used to generate a
representation from a string to show nested attributes and customize the representation if needed.

Functions:
    - truncate:
        A helper function used to truncate various types before representations of objects are displayed. This function
        also accounts for edge cases and type differences before other utilities display the repr.
    - generate_repr:
        The core representation generating function that uses the class type and attributes to create a representation
        of the object.
    - generate_repr_from_string:
        Takes a class name and dictionary of attribute name-value pairs to create a representation from scratch.
    - generate_sequence_repr:
        Generates a representation of a sequence given its class and internal elements. This class uses  `generate_repr`
        on each nested component to generate the complete the representation.
    - adjust_repr_padding:
        Helper function that adjusts the padding of the representation to ensure all attributes are shown in-line.
    - format_repr_value:
        Formats the value of a nested attribute with regard to padding and appearance with the selected options.
    - normalize_repr:
        Formats the value of a nested attribute, cleaning memory locations and stripping whitespace.

"""
from typing import Any, Optional, MutableSequence, Mapping, Sequence
from pydantic import BaseModel
from dataclasses import asdict, is_dataclass
import threading
import re
from scholar_flux.utils.helpers import as_tuple, quote_if_string

_LOCK_TYPE = type(threading.Lock())


def truncate(
    value: Any,
    max_length: int = 40,
    suffix: str = "...",
    show_count: bool = True,
) -> str:
    """Truncates various strings, mappings, and sequences for cleaner representations of objects in CLIs.

    Handles:
    - Strings: Truncate with suffix
    - Mappings (dict): Show preview of first N chars with count
    - Sequences (list, tuple): Show preview with count
    - Other objects: Use string representation

    Args:
        value (Any): The value to truncate.
        max_length (int): Maximum character length before truncation.
        suffix (str): String to append when truncated (default: "...").
        show_count (bool): Whether to show item count for collections.

    Returns:
        str: Truncated string representation.


    Examples:
        >>> truncate("A very long string that needs truncation", max_length=20)
        'A very long string...'

        >>> truncate({'key1': 'value1', 'key2': 'value2'}, max_length=30)
        "{'key1': 'value1', ...} (2 items)"

        >>> truncate([1, 2, 3, 4, 5], max_length=10)
        '[1, 2, ...] (5 items)'

        >>> truncate({'a': 1}, max_length=50, show_count=False)
        "{'a': 1}"

    """
    # Handle None explicitly
    if value is None:
        return "None"

    # Handle strings
    if isinstance(value, str):
        if len(value) <= max_length:
            return value
        return value[: max_length - len(suffix)] + suffix

    # Handle mappings (dict, etc.)
    if isinstance(value, Mapping):
        str_repr = str(value)
        if len(str_repr) <= max_length:
            return str_repr

        # Truncate and add count
        truncated = str_repr[: max_length - len(suffix) - 1] + suffix + str_repr[-1]
        if show_count:
            count_suffix = f" ({len(value)} items)" if len(value) != 1 else " (1 item)"
            return truncated + count_suffix
        return truncated

    # Handle sequences (list, tuple, but not strings)
    if isinstance(value, (MutableSequence, tuple)):
        str_repr = str(value)
        if len(str_repr) <= max_length:
            return str_repr

        # Truncate and add count
        truncated = str_repr[: max_length - len(suffix) - 1] + suffix + str_repr[-1]
        if show_count:
            count_suffix = f" ({len(value)} items)" if len(value) != 1 else " (1 item)"
            return truncated + count_suffix
        return truncated

    # Fallback: convert to string and truncate
    str_repr = str(value)
    if len(str_repr) <= max_length:
        return str_repr
    return str_repr[: max_length - len(suffix)] + suffix


def adjust_repr_padding(obj: Any, pad_length: Optional[int] = 0, flatten: Optional[bool] = None) -> str:
    """Helper method for adjusting the padding for representations of objects.

    Args:
        obj (Any): The object to generate an adjusted repr for
        pad_length (Optional[int]) : Indicates the additional amount of padding that should be added.
                                     Helpful for when attempting to create nested representations formatted
                                     as intended.
        flatten (bool): Indicates whether to use newline characters. This is false by default
    Returns:
        str: A string representation of the current object that adjusts the padding accordingly

    """
    representation = str(obj)

    if flatten:
        return ", ".join(line.strip() for line in representation.split(",\n"))

    representation_lines = representation.split("\n")

    pad_length = pad_length or 0

    if len(representation_lines) >= 2 and re.search(r"^[a-zA-Z_]+\(", representation) is not None:
        minimum_padding_match = re.match("(^ +)", representation_lines[1])

        if minimum_padding_match:
            minimum_padding = minimum_padding_match.group(1)
            adjusted_padding = " " * (pad_length + len(minimum_padding))
            representation = "\n".join(
                (re.sub(f"^{minimum_padding}", adjusted_padding, line) if idx >= 1 else line)
                for idx, line in enumerate(representation_lines)
            )

    return str(representation)


def normalize_repr(value: Any, replace_numeric: Optional[bool] = False) -> str:
    """Helper function for removing byte locations and surrounding signs from classes.

    Args:
        value (Any): A value whose representation is to be normalized
        replace_numeric (bool): Determines whether count values in strings should be replaced.

    Returns:
        str: A normalized string representation of the current value

    """
    value_string = value.__class__.__name__ if not isinstance(value, str) else value
    value_string = re.sub(r"\<(.*?) object at 0x[a-z0-9]+\>", r"\1", value_string)
    value_string = value_string.strip("<").strip(">")
    if replace_numeric:
        value_string = re.sub(r"\([0-9]+\)", "(...)", value_string)
        value_string = re.sub(r"\((len *=|length *=|count *=|n *=)?[0-9]+\)", r"(\1...)", value_string)
    return value_string


def format_repr_value(
    value: Any,
    pad_length: Optional[int] = None,
    show_value_attributes: Optional[bool] = None,
    flatten: Optional[bool] = None,
    replace_numeric: Optional[bool] = False,
) -> str:
    """Helper function for representing nested objects from custom classes.

    Args:
        value (Any): The value containing the repr to format
        pad_length (Optional[int]): Indicates the total additional padding to add for each individual line
        show_value_attributes (Optional[bool]):
            If False, all attributes within the current object will be replaced with '...'. (e.g., `StorageDevice(...)`)
        flatten (bool): Determines whether to show each individual value inline or separated by a newline character
        replace_numeric (bool): Determines whether count values in strings should be replaced.

    """

    # for basic objects, use strings, otherwise use the repr for BaseModels instead
    value = (
        f"'{value}'"
        if isinstance(value, str) and not re.search(r"^[a-zA-Z_]+\(", value)
        else (str(value) if not isinstance(value, BaseModel) else repr(value))
    )

    value = normalize_repr(value, replace_numeric=replace_numeric)

    # determine whether to show all nested parameters for the current attribute
    if show_value_attributes is False and re.search(r"^[a-zA-Z_]+\(.*[^\)]", str(value)):
        value = value.split("(")[0] + "(...)"

    # pad automatically for readability
    value = adjust_repr_padding(value, pad_length=pad_length, flatten=flatten)
    # remove object memory location wrapper from the string
    return value


def generate_repr_from_string(
    class_name: str,
    attribute_dict: dict[str, Any],
    show_value_attributes: Optional[bool] = None,
    flatten: Optional[bool] = False,
    replace_numeric: Optional[bool] = False,
    as_dict: Optional[bool] = False,
    flatten_nested: Optional[bool] = None,
) -> str:
    """Method for creating a basic representation of a custom object's data structure. Allows for the direct creation of
    a repr using the classname as a string and the attribute dict that will be formatted and prepared for representation
    of the attributes of the object.

    Args:
        class_name: The class name of the object whose attributes are to be represented.
        attribute_dict (dict): The dictionary containing the full list of attributes to
                               format into the components of a repr
        flatten (bool): Determines whether to show each individual value inline or separated by a newline character
        replace_numeric (bool): Determines whether count values in strings should be replaced.
        as_dict (Optional[bool]): Determines whether to represent the current class as a dictionary.
        flatten_nested (Optional[bool]):
            Indicates whether to use newline characters to create a representation of nested objects or to flatten
            them into a single line. False by default.

    Returns:
        A string representing the object's attributes in a human-readable format.

    """

    opening, closing, delimiter = ("(", ")", "=") if not as_dict else ("({", ")}", ": ")
    pad_length = len(class_name) + len(opening)
    pad = ",\n" + " " * pad_length if not flatten else ", "
    flatten_nested = flatten if flatten_nested is None else flatten_nested

    attribute_string = pad.join(
        f"{quote_if_string(attribute) if as_dict else attribute}{delimiter}"
        + format_repr_value(
            value,
            pad_length=pad_length + len(f"{attribute}") + 1,
            show_value_attributes=show_value_attributes,
            flatten=flatten_nested,
            replace_numeric=replace_numeric,
        )
        for attribute, value in attribute_dict.items()
    )
    return f"{class_name}{opening}{attribute_string or ''}{closing}"


def _resolve_attribute_name(obj: object, attribute: str, resolve_property: bool) -> str:
    """Helper function that resolves an object's private attribute to its public display name when available.

    Several objects often use private attributes (denoted with a leading underscore) for the validation of properties
    with `setter` methods to verify that the value takes on the correct type or value in context.

    When possible, this function maps these private attributes (`_current_attribute`) to public properties
    `current_attribute` when `resolve_property=True` and both exist in an object.

    Args:
        obj (object): The object containing the attribute.
        attribute (str): The private attribute name within the object (can be found in obj.__dict__).
        resolve_property: Whether to attempt property resolution. When false, the private attribute name is returned.

    Returns:
        The public display name when available and the original attribute otherwise.

    """
    if not resolve_property or not attribute.startswith("_") or attribute.startswith("__"):
        return attribute

    public_name = attribute[1:]
    class_attr = getattr(obj.__class__, public_name, None)
    if isinstance(class_attr, property):
        return public_name
    return attribute


def extract_attributes(
    obj: object, exclude: Optional[set[str] | list[str] | tuple[str]] = None, resolve_property_attributes: bool = False
) -> dict[str, Any]:
    """Helper function for extracting the core attributes and their values from data structures.

    Args:
        obj (object): The object whose attributes are to be represented.
        exclude (Optional[set[str] | list[str] | tuple[str]]):
            Attributes to exclude from the representation (None by default).
        resolve_property_attributes (bool): Determines whether to substitute properties pointing to private attributes.

    Returns:
        dict[str, Any]: A dictionary containing the object's attribute-value pairs.

    """
    exclude = set(as_tuple(exclude))
    match obj:
        case obj if is_dataclass(obj) and not isinstance(obj, type):
            return {field: value for field, value in asdict(obj).items() if field not in exclude}

        case BaseModel():
            return {field: value for field, value in dict(obj).items() if field not in exclude}

        case _:

            attribute_directory = set(dir(obj.__class__))
            attribute_keys = set(obj.__dict__.keys()) - attribute_directory

            attribute_dict = {
                resolved: value
                for attribute, value in obj.__dict__.items()
                if (resolved := _resolve_attribute_name(obj, attribute, resolve_property_attributes))
                and (attribute in attribute_keys or (resolve_property_attributes and attribute.startswith("_")))
                and resolved not in exclude
                and not callable(value)
                and not isinstance(value, _LOCK_TYPE)
            }
            return attribute_dict


def generate_repr(
    obj: object,
    exclude: Optional[set[str] | list[str] | tuple[str]] = None,
    show_value_attributes: bool = True,
    flatten: bool = False,
    replace_numeric: bool = False,
    as_dict: Optional[bool] = False,
    resolve_property_attributes: bool = False,
    flatten_nested: Optional[bool] = None,
) -> str:
    """Method for creating a basic representation of a custom object's data structure. Useful for showing the
    options/attributes being used by an object.

    In case the object doesn't have a __dict__ attribute, the code will raise an AttributeError and fall back to using
    the basic string representation of the object.

    Note that `threading.Lock` objects are excluded from the final representation.

    Args:
        obj: The object whose attributes are to be represented.
        exclude: Attributes to exclude from the representation (default is None).
        flatten (bool): Determines whether to show each individual value inline or separated by a newline character
        replace_numeric (bool): Determines whether count values in strings should be replaced.
        as_dict (bool): Determines whether to represent the current class as a dictionary.
        resolve_property_attributes (bool): Determines whether to substitute properties pointing to private attributes.
        flatten_nested (Optional[bool]):
            Indicates whether to use newline characters to create a representation of nested objects or to flatten
            them into a single line. If None, nested objects are flattened only if `flatten=True`.

    Returns:
        A string representing the object's attributes in a human-readable format.

    """
    # attempt to build a representation of the current object based on its attributes
    exclude = set(as_tuple(exclude))
    try:
        class_name = obj.__class__.__name__

        attribute_dict = extract_attributes(
            obj, exclude=exclude, resolve_property_attributes=resolve_property_attributes
        )

        return generate_repr_from_string(
            class_name,
            attribute_dict,
            show_value_attributes=show_value_attributes,
            flatten=flatten,
            replace_numeric=replace_numeric,
            as_dict=as_dict,
            flatten_nested=flatten_nested,
        )

    # if the class doesn't have an attribute such as __dict__, fall back to a simple str
    except AttributeError:
        return str(obj)


def generate_sequence_repr(
    obj: Sequence,
    flatten: bool = False,
    show_value_attributes: bool = True,
    replace_numeric: bool = False,
    brackets: Optional[tuple[str, str]] = ("[", "]"),
    flatten_nested: Optional[bool] = None,
) -> str:
    """Method for creating a basic representations for sequence-like data structures.

    This function generates formatted `str` representations for collections such as list, tuple, deque, and custom sequence
    data types. A string representation is also created for nested elements using `generate_repr` internally.

    When this function encounters an error, the method internally falls back to using the `str` function to create a basic
    string representation.

    Args:
        obj (Sequence): The sequence-like object to create a string representation for
        flatten (bool): Indicates whether to use newline characters. This is false by default
        show_value_attributes (bool): If False, nested attributes within elements will be
                                      replaced with '...'. e.g., `RetryAttempt(...)`
        replace_numeric (bool): Determines whether count values in strings should be replaced.
        brackets (Optional[tuple[str, str]]): Opening and closing brackets for the sequence (default: "[", "]").
        flatten_nested (Optional[bool]):
            Indicates whether to use newline characters to create a representation of nested objects or to flatten
            them into a single line. If None, nested objects are flattened only if `flatten=True`.

    Returns:
        A string representing the sequence's elements in a human-readable format.

    Examples:
        >>> from collections import deque
        >>> from scholar_flux.utils import generate_sequence_repr
        >>> items = deque([{"a": 1}, {"b": 2}])
        >>> print(generate_sequence_repr(items, flatten=True))
        # OUTPUT: deque([{'a': 1}, {'b': 2}])

        >>> print(generate_sequence_repr(items, flatten=False))
        # OUTPUT: deque([{'a': 1},
                         {'b': 2}])

        >>> print(generate_sequence_repr([1, 2, 3], flatten=True, brackets=None))
        # OUTPUT: list((1, 2, 3))

    """
    class_name = obj.__class__.__name__
    open_bracket, close_bracket = brackets if brackets else ("", "")

    base_indent = len(class_name) + 1 + len(open_bracket)
    flatten_nested = flatten if flatten_nested is None else flatten_nested

    formatted_elements = []
    for element in obj:
        element_repr = generate_repr(
            element,
            flatten=flatten_nested,
            show_value_attributes=show_value_attributes,
            replace_numeric=replace_numeric,
        )
        indented_element = adjust_repr_padding(element_repr, base_indent, flatten=flatten)
        formatted_elements.append(indented_element)

    sep = ",\n" + " " * base_indent if not flatten else ", "
    return f"{class_name}({open_bracket}{sep.join(formatted_elements)}{close_bracket})"


__all__ = [
    "truncate",
    "generate_repr",
    "generate_repr_from_string",
    "generate_sequence_repr",
    "format_repr_value",
    "normalize_repr",
    "adjust_repr_padding",
]
