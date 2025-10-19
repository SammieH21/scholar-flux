# /utils/paths/processing_path.py
"""Implements the ProcessingPath that is the most fundamental component in the scholar_flux JSON path processing trie
implementation.

The ProcessingPath is used to store a path processing representation that allows for extensive flexibility in the
creation, filtering, and discovery of nested keys in JSON structures.

"""
from __future__ import annotations
from typing import Union
import re
import logging
from copy import deepcopy
from typing import Optional, List, Tuple, Pattern, ClassVar
from dataclasses import dataclass, field
from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    InvalidPathDelimiterError,
    InvalidComponentTypeError,
    PathIndexingError,
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingPath:
    """A utility class to handle path operations for processing and flattening dictionaries.

    Args:
        components (Union[str, int, Tuple[str, ...], List[str], List[int], List[str | int]]):
            The initial path, either as a string or a list of strings. Any integers will be auto-converted
            to strings in the process of formatting the components of the path
        component_types (Optional[Union[Tuple[str, ...], List[str]]]):
           Optional metadata fields that can be used to annotate specific components of a path
        delimiter (str):
            The delimiter used to separate components in the path.

    Raises:
        InvalidProcessingPathError: If the path is neither a string nor a list of strings.
        InvalidPathDelimiterError: If the delimiter is invalid.

    Attributes:
        components (Tuple[str, ...]): A tuple of path components.
        delimiter (str): The delimiter used to separate components in the path.

    Examples:

        >>> from scholar_flux.utils import ProcessingPath
        >>> abc_path = ProcessingPath(['a', 'b', 'c'], delimiter ='//')
        >>> updated_path = abc_path / 'd'
        >>> assert updated_path.depth > 3 and updated_path[-1] == 'd'
        # OUTPUT: True
        >>> assert str(updated_path) == 'a//b//c//d'
        >>> assert updated_path.has_ancestor(abc_path)

    """

    components: Tuple[str, ...] = field(init=False)
    component_types: Optional[Tuple[str, ...]] = field(init=False, default=None)
    delimiter: str = field(init=False, default="")
    DEFAULT_DELIMITER: ClassVar[str] = "."  # Class-level default delimiter

    def __init__(
        self,
        components: Union[str, int, Tuple[str, ...], List[str], List[int], List[str | int]] = (),
        component_types: Optional[Union[Tuple[str, ...], List[str]]] = None,
        delimiter: Optional[str] = None,
    ):
        """Initializes the ProcessingPath. The inputs are first validated to ensure that the path components and
        delimiters are valid.

        Args:
            components: (Union[str, int, Tuple[str, ...], List[str], List[int], List[str | int]]):
                 The current path keys describing the path where each key represents a nested key in a JSON structure
            component_types: (Optional[Union[Tuple[str, ...], List[str]]]):
                An iterable of component types (used to annotate the components)
            delimiter: (Optional[str]):
                The separator used to indicate separate nested keys in a JSON structure. Defaults to the class default
                if not directly specified.

        """
        # Use object.__setattr__ to bypass immutability restrictions
        object.__setattr__(
            self,
            "delimiter",
            self._validate_delimiter(delimiter if delimiter is not None else self.DEFAULT_DELIMITER),
        )
        object.__setattr__(self, "components", self._validate_and_split_path(components))
        object.__setattr__(self, "component_types", self._validate_component_types(component_types))

    @staticmethod
    def _validate_delimiter(delimiter: str) -> str:
        """Validate the provided delimiter to ensure it's suitable for use in a ProcessingPath.

        Args:
            delimiter (str): The delimiter to validate.

        Returns:
            str: The validated delimiter.

        Raises:
            InvalidPathDelimiterError: If the delimiter is not a valid string.

        """

        if not isinstance(delimiter, str) or not delimiter:
            raise InvalidPathDelimiterError("Delimiter must be a non-empty string.")

        if delimiter.isspace():
            raise InvalidPathDelimiterError("Delimiter must not be a whitespace character.")

        if not len(set(delimiter).intersection(set(r"\/:<>|.%"))) > 0:
            raise InvalidPathDelimiterError(
                rf"Delimiter must not contain special characters like \ / : % * ? \" |\n received delimiter={delimiter}"
            )
        return delimiter

    def _validate_and_split_path(
        self, path: Union[str, int, Tuple[str, ...], List[str], List[int], List[str | int]]
    ) -> Tuple[str, ...]:
        """Helper method used to validate and prepare a tuple of path components on the instantiation of the
        ProcessingPath. After validation, the path is prepared, split and formatted depending on its input type.

        Args:
            path (Union[str, int, Tuple[str, ...], List[str], List[int], List[str | int]]):
                The path to validate and split. Note that all integers are auto-converted to strings

        Returns:
            Tuple[str, ...]: The validated tuple of path components.

        Raises:
            InvalidProcessingPathError: If the path is not a string, tuple, or a list of strings.

        """
        # If the path is a string, split it using the delimiter
        if isinstance(path, str):
            path = path.split(self.delimiter)

        if isinstance(path, int):
            path = [str(path)]

        # Convert tuple to list for easier manipulation
        if isinstance(path, tuple):
            path = list(path)

        # If path is the root ('') or an empty list/tuple, return root node
        if path is None or path in ("", [""], [], ("",)):
            return ("",)

        # Ensure the path is a list of non-empty strings
        if not isinstance(path, list) or not all(isinstance(p, (str, int)) for p in path):
            raise InvalidProcessingPathError("Path must be a list or tuple of strings.")

        ## Add a root path indicator
        # if not path[0] == '':
        #    path = [''] + path[1:]

        # Check for empty components in the path after stripping whitespace
        if any(not p.strip() for p in path[1:] if isinstance(p, str)):
            raise InvalidProcessingPathError("Non-root path components must be non-empty strings.")

        # Return the validated path as a tuple
        return tuple(str(p) if isinstance(p, int) else p for p in path)

    def _validate_component_types(
        self, component_types: Optional[Union[str, Tuple[str, ...], List[str]]] = None
    ) -> Optional[Tuple[str, ...]]:
        """Helper method that validates the component types that serve as metadata for each component. Upon validation,
        the component types are split into a tuple of strings depending on their initial type.

        Args:
            path (Union[str, Tuple[str, ...], List[str]]): The path to validate and split.

        Returns:
            Tuple[str, ...]: The validated tuple of path components.

        Raises:
            InvalidProcessingPathError: If the path is not a string, tuple, or a list of strings.

        """

        if component_types is None:
            return None
        # If the path is a string, split it using the delimiter
        if isinstance(component_types, str):
            component_types = component_types.split(self.delimiter)

        # Convert tuple to list for easier manipulation
        if isinstance(component_types, tuple):
            component_types = list(component_types)

        # Ensure the component_types is a list of non-empty strings or types
        if not isinstance(component_types, list) or not all(isinstance(p, str) for p in component_types):
            raise InvalidProcessingPathError("Path must be a list or tuple of strings or types.")

        if not component_types:
            return None

        if any(not p.strip() for p in component_types[1:]):
            raise InvalidProcessingPathError("Path components must be non-empty strings.")

        # determine length difference between node components and
        component_type_length_diff = self.depth - len(component_types)

        if not component_type_length_diff == 0:

            raise InvalidComponentTypeError(
                "When specified, the length of component_type must match the "
                f"depth of the Path:\n Component Type Length = {len(component_types)}, "
                f"Length of Components received: {len(component_types)}. "
            )

        return tuple(component_types)

    @staticmethod
    def infer_delimiter(
        path: Union[str, ProcessingPath],
        delimiters: list[str] = ["<>", "//", "/", ">", "<", "\\", "%", "."],
    ) -> Optional[str]:
        """Infer the delimiter used in the path string based on its string representation.

        Args:
            path (Union[str,ProcessingPath]): The path string to infer the delimiter from.
            delimiters (List[str]): A list of common delimiters to search for in the path.
            default_delimiter (str): The default delimiter to use if no delimiter is found.
        Returns:
            str: The inferred delimiter.

        """
        str_path = path.to_string() if isinstance(path, ProcessingPath) else path

        for delimiter in delimiters:
            if delimiter in str_path:
                return delimiter

        return None

    def update_delimiter(self, new_delimiter: str) -> ProcessingPath:
        """Update the delimiter of the current ProcessingPath with the provided new delimiter.

        This method creates a new ProcessingPath instance with the same components but replaces
        the existing delimiter with the specified `new_delimiter`.

        Args:
            new_delimiter (str): The new delimiter to replace the current one.

        Returns:
            ProcessingPath: A new ProcessingPath instance with the updated delimiter.

        Raises:
            InvalidPathDelimiterError: If the provided `new_delimiter` is not valid.

        Example:
            >>> processing_path = ProcessingPath('a.b.c', delimiter='.')
            >>> updated_path = processing_path.update_delimiter('/')
            >>> print(updated_path)  # Output: ProcessingPath(a/b/c)

        """
        validated_delimiter = self._validate_delimiter(new_delimiter)
        return ProcessingPath(self.components, self.component_types, validated_delimiter)

    @classmethod
    def to_processing_path(
        cls,
        path: Union[ProcessingPath, str, int, List[str], List[int], List[str | int]],
        component_types: Optional[list | tuple] = None,
        delimiter: Optional[str] = None,
        infer_delimiter: bool = False,
    ) -> ProcessingPath:
        """Convert an input to a ProcessingPath instance if it's not already.

        Args:
            path (Union[ProcessingPath, str, int, List[str], List[int], List[str | int]]): The input path to convert.
            component_types (list|tuple): The type of component associated with each path element
            delimiter (str): The delimiter to use if the input is a string.

        Returns:
            ProcessingPath: A ProcessingPath instance.

        Raises:
            InvalidProcessingPathError: If the input cannot be converted to a valid ProcessingPath.

        """
        if isinstance(path, cls):
            return path

        if delimiter is None:

            if not infer_delimiter:
                # logger.debug(f"Infer delimiter is set to False. Default delimiter {cls.DEFAULT_DELIMITER} will be used")
                delimiter = cls.DEFAULT_DELIMITER
            else:
                if isinstance(path, (list, int)):
                    raise InvalidProcessingPathError("Cannot infer delimiter for list of strings or integers")
                return cls.with_inferred_delimiter(path, component_types)

        if isinstance(path, (str, int, list)):
            return cls(path, component_types, delimiter)
        else:
            raise InvalidProcessingPathError(f"Cannot convert {type(path)} to {cls.__name__}.")

    @classmethod
    def with_inferred_delimiter(
        cls,
        path: Union[ProcessingPath, str],
        component_types: Optional[List | Tuple] = None,
    ) -> ProcessingPath:
        """Converts an input to a ProcessingPath instance if it's not already a processing path.

        Args:
            path (Union[ProcessingPath, str, List[str]]): The input path to convert.
            delimiter (str): The delimiter to use if the input is a string.
            component_type (list|tuple): The type of component associated with each path element

        Returns:
            ProcessingPath: A ProcessingPath instance.

        Raises:
            InvalidProcessingPathError: If the input cannot be converted to a valid ProcessingPath.

        """
        if not isinstance(path, (ProcessingPath, str)):
            raise InvalidProcessingPathError(f"Cannot infer delimiter for {type(path)}")

        path = path.to_string() if isinstance(path, ProcessingPath) else path
        delimiter = cls.infer_delimiter(path) or cls.DEFAULT_DELIMITER
        return cls(path, component_types, delimiter)

    @property
    def is_root(self) -> bool:
        """Check if the path represents the root node.

        Returns:
            bool: True if the path is root, False otherwise.

        """
        return self.components == ("",)

    def __str__(self) -> str:
        """Convert the ProcessingPath to its string representation.

        Returns:
            str: The string representation of the ProcessingPath.

        """
        return self.delimiter.join(self.components)

    def __getitem__(self, index: Union[int, slice]) -> ProcessingPath:
        """Retrieve a subset of the ProcessingPath components using indexing or slicing.

        Args:
            index (Union[int, slice]): The index or slice to retrieve components.

        Returns:
            ProcessingPath: A new ProcessingPath object with the selected components.

        Raises:
            IndexError: If the index is out of range.

        """
        if isinstance(index, int):
            return ProcessingPath(
                self.components[index],
                ((self.component_types[index],) if self.component_types is not None else None),
                self.delimiter,
            )
        elif isinstance(index, slice):
            start, stop, step = index.indices(len(self.components))
            return ProcessingPath(
                self.components[start:stop:step],
                (self.component_types[start:stop:step] if self.component_types is not None else None),
                self.delimiter,
            )
        else:
            raise IndexError(f"Invalid index for ProcessingPath: received {index}")

    def append(self, component: int | str, component_type: Optional[str] = None) -> ProcessingPath:
        """Append a component to the path and return a new ProcessingPath object.

        Args:
            component (str): The component to append.

        Returns:
            ProcessingPath: A new ProcessingPath object with the appended component.

        Raises:
            InvalidProcessingPathError: If the component is not a non-empty string.

        """
        if not isinstance(component, (int, str)) or component is None or component == "":
            raise InvalidProcessingPathError("Component must be a non-empty string.")
        if self.component_types and (not isinstance(component_type, str) or not component_type):
            raise InvalidProcessingPathError(
                "Component Type must be a non-empty string/type when a pre-existing component type is not None"
            )
        return ProcessingPath(
            self.components + (str(component),),
            (
                self.component_types + (component_type,)
                if self.component_types is not None and component_type is not None
                else None
            ),
            self.delimiter,
        )

    @property
    def depth(self) -> int:
        """Return the depth of the path.

        Returns:
            int: The number of components in the path.

        """
        return len(self.components) if self.components != ("",) else 0

    @property
    def record_index(self) -> int:
        """Extract the first element of the current path to determine the record number if the current path  refers back
        to a paginated structure.

        Returns:
            int: The first value, converted to an integer if possible

        Raises:
           PathIndexingError: if the first element of the path is not a numerical index

        """
        try:
            idx = self.components[0]
            return int(idx)
        except (IndexError, TypeError) as e:
            raise PathIndexingError(
                f"The first element of the current path, '{self}',  cannot be indexed as a record: {e}"
            )

    def is_ancestor_of(self, path: Union[str, ProcessingPath]) -> bool:
        """Determine whether the current path (self) is equal to or a subset/descendant path of the specified path.

        Args:
            path (ProcessingPath): The potential superset of (self) ProcessingPath.

        Returns:
            bool: True if 'self' is a subset of 'path'. False Otherwise.

        """
        if self.is_root:
            return True  # Root path is a subset of any path

        if isinstance(path, str):
            path = ProcessingPath.to_processing_path(path, delimiter=self.delimiter)

        if self.depth >= path.depth:
            return False

        return self[: self.depth] == path[: self.depth]

    def has_ancestor(self, path: Union[str, ProcessingPath]) -> bool:
        """Determine whether the provided path is equal to or a subset/descendant of the current path (self).

        Args:
            path (ProcessingPath): The potential subset/descendant of (self) ProcessingPath.

        Returns:
            bool: True if 'self' is a superset of 'path'. False Otherwise.

        """
        if self.is_root:
            return False  # Root path is a subset of any path

        if isinstance(path, str):
            path = ProcessingPath.to_processing_path(path, delimiter=self.delimiter)

        if self.depth <= path.depth:
            return False

        return self[: path.depth] == path[: path.depth]

    def replace(self, old: str, new: str) -> ProcessingPath:
        """Replace occurrences of a component in the path.

        Args:
            old (str): The component to replace.
            new (str): The new component to replace the old one with.

        Returns:
            ProcessingPath: A new ProcessingPath object with the replaced components.

        Raises:
            InvalidProcessingPathError: If the replacement arguments are not strings.

        """
        if not isinstance(old, str) or not isinstance(new, str):
            raise InvalidProcessingPathError(
                f"Replacement arguments must be strings, received: old = {old}, new = {new}"
            )
        return ProcessingPath(
            tuple(new if comp == old else comp for comp in self.components),
            self.component_types,
            self.delimiter,
        )

    def replace_path(
        self,
        old: Union[str, ProcessingPath],
        new: Union[str, ProcessingPath],
        component_types: Optional[List | Tuple] = None,
    ) -> ProcessingPath:
        """Replace an ancestor path or full path in the current ProcessingPath with a new path.

        Args:
            old (Union[str, ProcessingPath]): The path to replace.
            new (Union[str, ProcessingPath]): The new path to replace the old path ancestor or full path with.

        Returns:
            ProcessingPath: A new ProcessingPath object with the replaced components.

        Raises:
            InvalidProcessingPathError: If the replacement arguments are not strings or ProcessingPaths.

        """
        if not isinstance(old, (str, ProcessingPath)) or not isinstance(new, (str, ProcessingPath)):
            raise InvalidProcessingPathError(
                f"Replacement arguments must be strings or ProcessingPaths, received: old = {old}, new = {new}"
            )

        old = ProcessingPath.to_processing_path(old, None, self.delimiter)
        new = ProcessingPath.to_processing_path(
            new,
            component_types if self.component_types is not None else None,
            self.delimiter,
        )
        if self == old:
            return new

        if self.has_ancestor(old):
            return new / self[old.depth :]

        return self

    def __hash__(self) -> int:
        """Compute a hash value for the ProcessingPath based on its components.

        Returns:
            int: The hash value of the ProcessingPath.

        """
        # return hash((self.components, self.delimiter))
        return hash(str(self))

    def __contains__(self, value: object) -> bool:
        """Method for indicating whether a partial path is contained within the ProcessingPath.

        This method uses string operations to account for delimiters to determine whether there is a match

        """

        if not isinstance(value, (list, tuple, str, ProcessingPath)):
            return False

        if isinstance(value, (list, tuple)):
            path = ProcessingPath(value)
        else:
            path = ProcessingPath.with_inferred_delimiter(value)

        return path.update_delimiter("<<>>").to_string() in self.update_delimiter("<<>>").to_string()

    def __lt__(self, path: ProcessingPath) -> bool:
        """Check if the current path is a subset of the given path and has a different depth.

        Args:
            path (ProcessingPath): The path to compare against.

        Returns:
            bool: True if self is a subset of path and has a different depth, otherwise False.

        """
        path = ProcessingPath.to_processing_path(path, delimiter=self.delimiter)
        return self._to_alphanum() < path._to_alphanum()

    def __le__(self, path: ProcessingPath) -> bool:
        """Check if the current path is equal to or a subset of the given path.

        Args:
            path (ProcessingPath): The path to compare against.

        Returns:
            bool: True if self is equal to or a subset of path, otherwise False.

        """
        path = ProcessingPath.to_processing_path(path, delimiter=self.delimiter)
        return self._to_alphanum() <= path._to_alphanum()

    def __gt__(self, path: ProcessingPath) -> bool:
        """Check if the current path strictly contains the given path.

        Args:
            path (ProcessingPath): The path to compare against.

        Returns:
            bool: True if self strictly contains path, otherwise False.

        """
        path = ProcessingPath.to_processing_path(path, delimiter=self.delimiter)
        return self._to_alphanum() > path._to_alphanum()

    def __ge__(self, path: ProcessingPath) -> bool:
        """Check if the current path is equal to or strictly contains the given path.

        Args:
            path (ProcessingPath): The path to compare against.

        Returns:
            bool: True if self is equal to or strictly contains path, otherwise False.

        """
        path = ProcessingPath.to_processing_path(path, delimiter=self.delimiter)
        return self._to_alphanum() >= path._to_alphanum()

    def __eq__(self, other: object) -> bool:
        """Check equality with another ProcessingPath, string, or list of strings.

        Args:
            other (object): The object to compare with.

        Returns:
            bool: True if the objects are equal, False otherwise.

        """
        if isinstance(other, ProcessingPath):
            return self.components == other.components and self.delimiter == other.delimiter
        elif isinstance(other, str):
            return self.components == ProcessingPath(other, delimiter=self.delimiter).components
        elif isinstance(other, (tuple, list)):
            return self.components == tuple(other)
        return False

    def __ne__(self, other: object) -> bool:
        """Check inequality with another ProcessingPath, string, or list of strings.

        Args:
            other (object): The object to compare with.

        Returns:
            bool: True if the objects are not equal, False otherwise.

        """
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        """Determine whether the current path is empty or non-empty.

        Returns:
            bool: Indicates whether the number of components is non-zero

        """
        return not self.is_root

    def __len__(self) -> int:
        """Helper method that retrieves the total number of components from the processing path.

        Excludes the root component in the calculation.

        Returns:
            int: The total number of components in the processing path

        """
        return self.depth

    def __truediv__(self, other: Union[ProcessingPath, str]) -> ProcessingPath:
        """Concatenate the ProcessingPath with another path using the '/' operator.

        Args:
            other (Union[ProcessingPath, str]): The other path to concatenate.

        Returns:
            ProcessingPath: A new ProcessingPath object with concatenated components.

        Raises:
            InvalidProcessingPathError: If the other path is neither a ProcessingPath nor a string.

        """
        new_component_types = None
        if isinstance(other, ProcessingPath):
            if other.is_root:
                return self.copy()
            new_components = self.components + other.components
            if self.component_types and other.component_types:
                new_component_types = self.component_types + other.component_types
        elif isinstance(other, str):
            if other == "":
                return self.copy()
            new_components = self.components + (other,)
        else:
            raise InvalidProcessingPathError(f"Can only concatenate with a ProcessingPath or string. Received: {other}")
        return ProcessingPath(new_components, new_component_types, delimiter=self.delimiter)

    def sorted(self) -> ProcessingPath:
        """Returns a sorted ProcessingPath from the current_path. Elements are sorted by component in alphabetical
        order.

        Returns:
           ProcessingPath: A new ProcessingPath object with the same components/types in a reversed order

        """

        ordered_indices, _ = zip(
            *sorted(
                enumerate(self._to_alphanum().split(self.delimiter)[1:]),
                key=lambda comp: comp[1],
            )
        )
        ordered_components = [self.components[i] for i in ordered_indices]
        ordered_component_types = [self.component_types[i] for i in ordered_indices] if self.component_types else None

        return ProcessingPath(ordered_components, ordered_component_types, self.delimiter)

    def __reversed__(self) -> ProcessingPath:
        """Helper method to reverse the ProcessingPath using the `reversed` built-in method."""
        return self.reversed()

    def reversed(self) -> ProcessingPath:
        """Returns a reversed ProcessingPath from the current_path.

        Returns:
           ProcessingPath: A new ProcessingPath object with the same components/types in a reversed order

        """
        return ProcessingPath(
            self.components[::-1],
            self.component_types[::-1] if self.component_types is not None else None,
            self.delimiter,
        )

    def copy(self) -> ProcessingPath:
        """Create a copy of the ProcessingPath.

        Returns:
            ProcessingPath: A new ProcessingPath object with the same components and delimiter.

        """
        return deepcopy(self)

    def to_string(self) -> str:
        """Get the string representation of the ProcessingPath.

        Returns:
            str: The string representation of the ProcessingPath.

        """
        return str(self)

    def to_pattern(self, escape_all=False) -> Pattern:
        """Convert the ProcessingPath to a regular expression pattern.

        Returns:
            Pattern: The regular expression pattern representing the ProcessingPath.

        """
        return (
            re.compile(re.escape(self.delimiter).join(self.components))
            if not escape_all
            else re.compile(re.escape(self.delimiter.join(self.components)))
        )

    def to_list(self) -> List[str]:
        """Convert the ProcessingPath to a list of components.

        Returns:
            List[str]: A list of components in the ProcessingPath.

        """
        return list(self.components)

    def _to_alphanum(self, pad: int = 8, depth_first: bool = True) -> str:
        """Generate an alphanumeric representation of the path, padding numeric components for sorting.

        Args:
            pad (int): The number of digits to pad numeric components (default is 8).
            depth_first (bool): Determines whether to sort, accounting for depth first prior to human sorted alphabetical path.

        Returns:
            str: The alphanumeric string representation of the ProcessingPath.

        Raises:
            InvalidProcessingPathError: If an error occurs during conversion.

        """
        try:
            padded_components = [
                re.sub(
                    r"(^[a-zA-Z_\.\-]*)(\d+)$",
                    lambda x: f"{x.group(1)!r}{x.group(2).zfill(pad)!r}",
                    comp,
                )
                for comp in self.components
            ]
            return self.delimiter.join([str(self.depth)] + padded_components if depth_first else padded_components)
        except Exception as e:
            raise InvalidProcessingPathError(f"Error generating alphanumeric representation for path '{self}': {e}")

    def _filter_indices_list(
        self, indices: List[int], include_matches: bool = False
    ) -> Tuple[Tuple[str, ...], Optional[Tuple[str, ...]]]:
        """Filter the current ProcessingPath using a list of indices and returns components and component types as a
        tuple."""
        filtered_components = tuple(
            [component for index, component in enumerate(self.components) if (index in indices) == include_matches]
        )

        filtered_component_types = None
        if self.component_types is not None:
            filtered_component_types = tuple(
                [
                    component_type
                    for index, component_type in enumerate(self.component_types)
                    if (index in indices) == include_matches
                ]
            )
        return filtered_components, filtered_component_types

    def remove_indices(self, num: int = -1, reverse: bool = False) -> ProcessingPath:
        """Remove numeric components from the path.

        Args:
            num (int): The number of numeric components to remove. If negative, removes all (default is -1).
        Returns:
            ProcessingPath: A new ProcessingPath object without the specified numeric components.

        """

        filtered_indices = [index for index, component in enumerate(self.components) if component.isdigit()]

        if not filtered_indices:
            return self.copy()

        if reverse:
            filtered_indices.reverse()

        if num >= 0:
            filtered_indices = filtered_indices[:num]

        filtered_components, filtered_component_types = self._filter_indices_list(
            filtered_indices, include_matches=False
        )

        return ProcessingPath(tuple(filtered_components), filtered_component_types, self.delimiter)

    def replace_indices(self, placeholder: str = "i") -> ProcessingPath:
        """Replace numeric components in the path with a placeholder.

        Args:
            placeholder (str): The placeholder to replace numeric components with (default is 'i').

        Returns:
            ProcessingPath: A new ProcessingPath object with numeric components replaced by the placeholder.

        """
        new_components = tuple(placeholder if component.isdigit() else component for component in self.components)
        return ProcessingPath(new_components, self.component_types, self.delimiter)

    def get_parent(self, step: int = 1) -> Optional[ProcessingPath]:
        """Get the ancestor path of the current ProcessingPath by the specified number of steps.

        This method navigates up the path structure by the given number of steps. If the step count is greater than or
        equal to the depth of the current path, or if the path is already the root, it returns None. If the step count
        equals the current depth, it returns the root ProcessingPath.

        Args:
            step (int): The number of levels up to retrieve. 1 for parent, 2 for grandparent, etc. (default is 1).

        Returns:
            Optional[ProcessingPath]:
                - The ancestor ProcessingPath if the step is within the path depth.
                - The root ProcessingPath if step equals the depth of the current path.
                - None if the step is greater than the current depth or if the path is already the root.

        Raises:
            ValueError: If the step is less than 1.

        """
        if step < 1:
            raise ValueError("Step must be greater than or equal to 1.")
        if self.is_root or step > len(self.components):
            return None
        if step == len(self.components):
            return ProcessingPath([""])
        return ProcessingPath(
            self.components[:-step],
            self.component_types[:-step] if self.component_types else None,
            self.delimiter,
        )

    def get_ancestors(self) -> List[Optional[ProcessingPath]]:
        """Get all parent paths of the current ProcessingPath by the specified number of steps.

        Returns:
            List[Optional[ProcessingPath]]:
                - Contains a list of all ancestor paths for the current path
                - If the depth of the path is 1, an empty list is returned

        """
        if self.is_root:
            return []
        return [self.get_parent(i) for i in range(1, self.depth)]

    def remove(self, removal_list: List[str]) -> ProcessingPath:
        """Remove specified components from the path.

        Args:
            removal_list (List[str]): A list of components to remove.

        Returns:
            ProcessingPath: A new ProcessingPath object without the specified components.

        """
        filtered_indices = [index for index, comp in enumerate(self.components) if comp not in removal_list]

        filtered_components, filtered_component_types = self._filter_indices_list(
            filtered_indices, include_matches=True
        )

        return ProcessingPath(filtered_components, filtered_component_types, self.delimiter)

    def remove_by_type(self, removal_list: List[str], raise_on_error: bool = False) -> ProcessingPath:
        """Remove specified component types from the path.

        Args:
            removal_list (List[str]): A list of component types to remove.

        Returns:
            ProcessingPath: A new ProcessingPath object without the specified components.

        """
        if self.component_types is None:
            if raise_on_error:
                raise InvalidComponentTypeError("The ProcessingPath has no component type is available to filter on")
            else:
                logger.warning("The ProcessingPath has no component type is available to filter on. Skipping filtering")
                return self.copy()

        filtered_indices = [index for index, comp in enumerate(self.component_types) if comp not in removal_list]

        filtered_components, filtered_component_types = self._filter_indices_list(
            filtered_indices, include_matches=True
        )

        return ProcessingPath(filtered_components, filtered_component_types, self.delimiter)

    def info_content(self, non_informative: List[str]) -> int:
        """Calculate the number of informative components in the path.

        Args:
            non_informative (List[str]): A list of non-informative components.

        Returns:
            int: The number of informative components.

        """
        informative_path = self.remove(non_informative)
        return len(informative_path.components)

    def get_name(self, max_components: int = 1) -> ProcessingPath:
        """Generate a path name based on the last 'max_components' components of the path.

        Args:
            max_components (int): The maximum number of components to include in the name (default is 1).

        Returns:
            ProcessingPath: A new ProcessingPath object representing the generated name.

        """
        return ProcessingPath(
            self.components[-max_components:],
            (self.component_types[-max_components:] if self.component_types is not None else None),
            self.delimiter,
        )

    @classmethod
    def keep_descendants(cls, paths: List[ProcessingPath]) -> List[ProcessingPath]:
        """Filters a list of paths and keeps only descendants."""
        if not paths:
            return []

        prepared_paths = [path if isinstance(path, cls) else cls.with_inferred_delimiter(path) for path in paths]

        sorted_paths = sorted(prepared_paths, key=lambda path: path.depth)
        max_depth = sorted_paths[-1].depth

        result = [
            current_path
            for i, current_path in enumerate(sorted_paths)
            if current_path.depth == max_depth
            or not any(current_path.is_ancestor_of(p) for p in sorted_paths[i + 1 :] if current_path.depth < p.depth)
        ]

        return result

    def group(self, last_only: bool = False) -> ProcessingPath:
        """Attempt to retrieve the path omitting the last element if it is numeric. The remaining integers are replaced
        with a placeholder (i). This is later useful for when we need to group paths into a list or sets in order to
        consolidate record fields.

        Args:
            last_only (bool): Determines whether or not to replace all list indices vs removing only the last

        Returns:
            ProcessingPath: A ProcessingPath instance with the last numeric component removed and indices replaced.

        """

        if not self:
            return self

        if any(
            [
                self.component_types and self.component_types[-1] == "list",
                self.components[-1].isnumeric(),
            ]
        ):

            return self.remove_indices(num=1, reverse=True).replace_indices()

        return self.replace_indices()

    def __repr__(self) -> str:
        """Get the string representation of the ProcessingPath object.

        Returns:
            str: The string representation of the ProcessingPath.

        """
        return f"ProcessingPath(components={self.delimiter.join(self.components)}, component_types={self.delimiter.join(self.component_types) if self.component_types else None})"


__all__ = ["ProcessingPath"]
