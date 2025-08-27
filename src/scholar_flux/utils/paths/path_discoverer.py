from __future__ import annotations
from typing import Optional, Union, Any, Set, ClassVar
from dataclasses import dataclass, field
from scholar_flux.exceptions.path_exceptions import PathDiscoveryError



from scholar_flux.utils.paths import ProcessingPath
from scholar_flux.utils import is_nested

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

@dataclass
class PathDiscoverer:
    """
    For both discovering paths and
    flattening json files into a single
    dictionary that simplifies the nested structure into the
    path, the type of structure, and the terminal value.

    Args:
        records: Optional[Union[list[dict], dict]]: A list of dictionaries to be flattened
        path_mappings: dict[ProcessingPath, Any]: A set of key-value pairs
                                                  mapping paths to terminal values
    Attributes:
        records: The input data to be traversed and flattened.
        path_mappings: Holds a dictionary of values mapped to ProcessingPaths after processing
    """
    records: Optional[Union[list[dict], dict]] = None
    path_mappings: dict[ProcessingPath, Any] = field(default_factory=dict)
    DEFAULT_DELIMITER: ClassVar[str] = ProcessingPath.DEFAULT_DELIMITER


    @property
    def terminal_paths(self) -> Set[ProcessingPath]:
        return set(self.path_mappings.keys())


    def discover_path_elements(self, records: Optional[Union[list[dict], dict]] = None,
                               current_path: Optional[ProcessingPath]=None,
                               max_depth: Optional[int] = None,
                               inplace: bool=False
                              ) -> Optional[dict[ProcessingPath, Any]]:
        """
        Recursively traverses records to discover keys, their paths, and terminal status. Uses the
        private method _discover_path_elements in order to add terminal path value pairs to the
        path_mappings attribute.

        Args:
            records (Optional[Union[list[dict], dict]]): A list of dictionaries to be flattened if not already provided.
            current_path (Optional[dict[ProcessingPath, Any]]): The parent path to prefix all subsequent paths with.
                                                                Is useful when working with a subset of a dict
            max_depth (Optional[int]): Indicates the times we should recursively attempt to retrieve a terminal path.
                                       Leaving this at None will traverse all possible nested lists/dictionaries.
            inplace (bool): Determines whether or not to save the inner state of the PathDiscoverer object.
                            When False: Returns the final object and clears the self.path_mappings attribute.
                            When True: Retains the self.path_mappings attribute and returns None
        """

        records = records or self.records
        try:
            if records is None:
                raise ValueError("The value provided to 'records' is invalid: No data to process.")

            current_path = current_path or ProcessingPath(delimiter=self.DEFAULT_DELIMITER)
            self.path_mappings[current_path]=None

            # record the next element deep if max_depth has not already been reached
            recursive = max_depth is None or current_path.depth < max_depth
            if recursive:
                self._discover_path_elements(records,
                                             current_path,
                                             max_depth = max_depth)

            if not inplace:
                mappings = self.path_mappings.copy()
                self.clear()
                return mappings

        except ValueError as e:
            logger.error(f"A Value error was encountered during path discovery: {e}")
            raise PathDiscoveryError from e

        except TypeError as e:
            logger.error(f"An unsupported type was encountered during path discovery: {e}")
            raise PathDiscoveryError from e


        return None

    def _discover_path_elements(self,
                                record: Any,
                                current_path: ProcessingPath,
                                max_depth: Optional[int] = None,
                               ):
        """
        Helper funtion for recursively traversing a dictionary and adding terminal path - value pairs where they exist.
        In the event that a max depth parameter is specified, the code will attempt to retrieve terminal paths only up
        to the depth specified by max_depth.

        Args:
            records (Optional[list[dict]]): A list of dictionaries to be flattened if not already provided.
            current_path (Optional[dict[ProcessingPath, Any]]): The parent path to prefix all subsequent paths with.
                                                                Is useful when working with a subset of a dict.
            max_depth (Optional[int]): Indicates the times we should recursively attempt to retrieve a terminal path.
                                       Leaving this at None will traverse all possible nested lists/dictionaries.
        """
        try:
            # continue recursively recording path nodes if we have not exceeded a nonmissing max_depth
            recursive = max_depth is None or current_path.depth <= max_depth
            if isinstance(record, dict):
                for key, value in record.items():

                    # records the current key and the type of its value pair into a path
                    path_node = ProcessingPath(str(key), ('dict',))

                    # ensure that the first element of a path starts with an indexable key
                    new_path = current_path / path_node if current_path.depth else path_node

                    if is_nested(value):
                        if recursive:

                            # pop a previous path if exists
                            self.path_mappings.pop(current_path,None)

                            # keep traversing the structure for a terminal path
                            self._discover_path_elements(
                                value,
                                new_path,
                                max_depth
                            )

                        else:
                            self._log_early_stop(new_path, value)
                    else:
                        self.path_mappings[new_path] = value
                        self._log_recorded_paths(new_path, value)

            elif isinstance(record, list):
                # process lists with indices serving as keys
                for index, item in enumerate(record):
                    path_node = ProcessingPath(str(index), ('list',),delimiter=self.DEFAULT_DELIMITER)
                    new_path = current_path / path_node if current_path.depth else path_node

                    # determine whether the next value is a nested structure (non-str iterable)
                    if is_nested(item):
                        if recursive:

                            # removes a previous pair if exists
                            self.path_mappings.pop(current_path,None)

                            # keep traversing the structure for a terminal path
                            self._discover_path_elements(
                                item,
                                new_path,
                                max_depth
                            )
                        else:
                             self._log_early_stop(new_path, item)

                    else:
                        self.path_mappings[new_path] = item
                        self._log_recorded_paths(new_path, item)
            else:
                raise TypeError(f"The data type for record, '{type(record)}', is unsupported.")
        except TypeError as e:
            logger.error(f'Type error encountered during traversal of the path, {current_path}: {e}')
            raise

    @staticmethod
    def _log_early_stop(path: ProcessingPath, value: Any, max_depth: Optional[int] = None):
        """
        Logs the resulting value after stopping the addition of paths early by max depth.

        Args:
            path (ProcessingPath): The path where traversal stopped.
            value (Any): The terminal value at this path.
            max_depth (Optional[int]): Maximum depth for recursion.
        """
        value_str = f"{str(value)[:30]}..." if len(str(value)) > 30 else str(value)
        logger.warning(f"Max_depth ({max_depth}) of path retrieval exceeded: stopped retrieval of path {path} early. Value ({type(value)}) = {value_str}")

    @staticmethod
    def _log_recorded_paths(path: ProcessingPath, value: Any):
        """
        Logs the resulting value after adding a terminal path.

        Args:
            path (ProcessingPath): The path being logged.
            value (Any): The terminal value at this path.
        """
        value_str = f"{str(value)[:30]}..." if len(str(value)) > 30 else str(value)
        logger.debug(f'Recorded path {path}. Value ({type(value)}) = {value_str}...')

    def clear(self):
        """Removes all path-value mappings from the self.path_mappings dictionary."""
        self.path_mappings.clear()
        logger.debug('Cleared all paths from the Discoverer...')
