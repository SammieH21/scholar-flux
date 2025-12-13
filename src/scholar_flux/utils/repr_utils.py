# /utils/repr_utils.py
"""The scholar_flux.utils.repr_utils module includes several methods used in the creation of descriptive representations
of custom objects such as custom classes, dataclasses, and base models. This module can be used to generate a
representation from a string to show nested attributes and customize the representation if needed.

Functions:
    - truncate: A helper function used to truncate various types before representations of objects are displayed.
                This function also accounts for edge cases and type differences before other utilities display the repr.
    - generate_repr: The core representation generating function that uses the class type and attributes
                     to create a representation of the object
    - generate_repr_from_string: Takes a class name and dictionary of attribute name-value pairs to create
                                 a representation from scratch
    - adjust_repr_padding: Helper function that adjusts the padding of the representation to ensure all
                           attributes are shown in-line
    - format_repr_value: Formats the value of a nested attribute with regard to padding and appearance with
                         the selected options
    - normalize_repr: Formats the value of a nested attribute, cleaning memory locations and stripping whitespace

"""
from typing import Any, Optional, MutableSequence, Mapping
from pydantic import BaseModel
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
        value: The value to truncate
        max_length: Maximum character length before truncation
        suffix: String to append when truncated (default: "...")
        show_count: Whether to show item count for collections

    Returns:
        Truncated string representation

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
        show_value_attributes (Optional[bool]): If False, all attributes within the current object
                                                 will be replaced with '...'. As an example: e.g. StorageDevice(...)
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

    Returns:
        A string representing the object's attributes in a human-readable format.

    """

    opening, closing, delimiter = ("(", ")", "=") if not as_dict else ("({", ")}", ": ")
    pad_length = len(class_name) + len(opening)
    pad = ",\n" + " " * pad_length if not flatten else ", "

    attribute_string = pad.join(
        f"{quote_if_string(attribute) if as_dict else attribute}{delimiter}"
        + format_repr_value(
            value,
            pad_length=pad_length + len(f"{attribute}") + 1,
            show_value_attributes=show_value_attributes,
            flatten=flatten,
            replace_numeric=replace_numeric,
        )
        for attribute, value in attribute_dict.items()
    )
    return f"{class_name}{opening}{attribute_string or ''}{closing}"


def generate_repr(
    obj: object,
    exclude: Optional[set[str] | list[str] | tuple[str]] = None,
    show_value_attributes: bool = True,
    flatten: bool = False,
    replace_numeric: bool = False,
    as_dict: Optional[bool] = False,
) -> str:
    """Method for creating a basic representation of a custom object's data structure. Useful for showing the
    options/attributes being used by an object.

    In case the object doesn't have a __dict__ attribute,
    the code will raise an AttributeError and fall back to
    using the basic string representation of the object.

    Note that `threading.Lock` objects are excluded from the final representation.

    Args:
        obj: The object whose attributes are to be represented.
        exclude: Attributes to exclude from the representation (default is None).
        flatten (bool): Determines whether to show each individual value inline or separated by a newline character
        replace_numeric (bool): Determines whether count values in strings should be replaced.
        as_dict (bool): Determines whether to represent the current class as a dictionary.

    Returns:
        A string representing the object's attributes in a human-readable format.

    """
    # attempt to build a representation of the current object based on its attributes
    try:
        class_name = obj.__class__.__name__
        attribute_directory = set(dir(obj.__class__))
        attribute_keys = set((obj.__dict__.keys())) - attribute_directory
        exclude = as_tuple(exclude)

        attribute_dict = {
            attribute: value
            for attribute, value in obj.__dict__.items()
            if attribute in attribute_keys
            and not callable(value)
            and attribute not in exclude
            and not isinstance(value, _LOCK_TYPE)
        }

        return generate_repr_from_string(
            class_name,
            attribute_dict,
            show_value_attributes=show_value_attributes,
            flatten=flatten,
            replace_numeric=replace_numeric,
            as_dict=as_dict,
        )

    # if the class doesn't have an attribute such as __dict__, fall back to a simple str
    except AttributeError:
        return str(obj)


__all__ = [
    "truncate",
    "generate_repr",
    "generate_repr_from_string",
    "format_repr_value",
    "normalize_repr",
    "adjust_repr_padding",
]
