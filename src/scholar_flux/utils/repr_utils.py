# /utils/repr_utils.py
"""The scholar_flux.utils.repr_utils module includes several methods used in the creation of descriptive representations
of custom objects such as custom classes, dataclasses, and base models. This module can be used to generate a
representation from a string to show nested attributes and customize the representation if needed.

Functions:
    - generate_repr: The core representation generating function that uses the class type and attributes
                     to create a representation of the object
    - generate_repr_from_string: Takes a class name and dictionary of attribute name-value pairs to create
                                 a representation from scratch
    - adjust_repr_padding: Helper function that adjusts the padding of the representation to ensure all
                           attributes are shown in-line
    - format_repr_value: Formats the value of a nested attribute regarding padding and appearance with
                         the selected options
    - normalize_repr: Formats the value of a nested attribute, cleaning memory locations and stripping whitespace

"""
from typing import Any, Optional
from pydantic import BaseModel
import threading
import re
from scholar_flux.utils.helpers import as_tuple


_LOCK_TYPE = type(threading.Lock())


def adjust_repr_padding(obj: Any, pad_length: Optional[int] = 0, flatten: Optional[bool] = None) -> str:
    """Helper method for adjusting the padding for representations of objects.

    Args:
        obj (Any): The object to generate an adjusted repr for
        pad_length (Optional[int]) : Indicates the additional amount of padding that should be added.
                                     Helpful for when attempting to create nested representations formatted
                                     as intended.
        flatten (bool): indicates whether to use newline characters. This is false by default
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


def normalize_repr(value: Any) -> str:
    """Helper function for removing byte locations and surrounding signs from classes.

    Args:
        value (Any): a value whose representation to be normalized

    Returns:
        str: A normalized string representation of the current value

    """
    value_string = value.__class__.__name__ if not isinstance(value, str) else value
    value_string = re.sub(r"\<(.*?) object at 0x[a-z0-9]+\>", r"\1", value_string)
    value_string = value_string.strip("<").strip(">")
    return value_string


def format_repr_value(
    value: Any,
    pad_length: Optional[int] = None,
    show_value_attributes: Optional[bool] = None,
    flatten: Optional[bool] = None,
) -> str:
    """Helper function for representing nested objects from custom classes.

    Args:
        value (Any): The value containing the repr to format
        pad_length (Optional[int]): Indicates the total additional padding to add for each individual line
        show_value_attributes (Optional[bool]): If False, all attributes within the current object
                                                 will be replaced with '...'. As an example: e.g. StorageDevice(...)
        flatten (bool): Determines whether to show each individual value inline or separated by a newline character

    """

    # for basic objects, use strings, otherwise use the repr for BaseModels instead
    value = (
        f"'{value}'"
        if isinstance(value, str) and not re.search(r"^[a-zA-Z_]+\(", value)
        else (str(value) if not isinstance(value, BaseModel) else repr(value))
    )

    value = normalize_repr(value)

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
) -> str:
    """Method for creating a basic representation of a custom object's data structure. Allows for the direct creation of
    a repr using the classname as a string and the attribute dict that will be formatted and prepared for representation
    of the attributes of the object.

    Args:
        class_name: The class name of the object whose attributes are to be represented.
        attribute_dict (dict): The dictionary containing the full list of attributes to
                               format into the components of a repr
        flatten (bool): Determines whether to show each individual value inline or separated by a newline character

    Returns:
        A string representing the object's attributes in a human-readable format.

    """
    pad_length = len(class_name) + 1
    pad = ",\n" + " " * pad_length if not flatten else ", "
    attribute_string = pad.join(
        f"{attribute}="
        + format_repr_value(
            value,
            pad_length=pad_length + len(f"{attribute}") + 1,
            show_value_attributes=show_value_attributes,
            flatten=flatten,
        )
        for attribute, value in attribute_dict.items()
    )
    return f"{class_name}({attribute_string or ''})"


def generate_repr(
    obj: object,
    exclude: Optional[set[str] | list[str] | tuple[str]] = None,
    show_value_attributes: bool = True,
    flatten: bool = False,
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
        )

    # if the class doesn't have an attribute such as __dict__, fall back to a simple str
    except AttributeError:
        return str(obj)


__all__ = [
    "generate_repr",
    "generate_repr_from_string",
    "format_repr_value",
    "normalize_repr",
    "adjust_repr_padding",
]
