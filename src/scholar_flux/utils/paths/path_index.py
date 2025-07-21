# scholar_flux.utils.path_index
from __future__ import annotations
import re
import copy
from typing import Optional, List, Dict, Union, Any, Tuple, Pattern, Set, ClassVar, Hashable, Callable, Iterable, Generator, Iterator, Mapping
from collections import defaultdict
from dataclasses import dataclass, field
from collections import UserDict
from collections.abc import Iterator
from scholar_flux.exceptions.path_exceptions import (InvalidPathNodeError,
                                                     InvalidProcessingPathError,
                                                     PathIndexingError,
                                                     PathNodeIndexError,
                                                     PathCacheError,
                                                     PathNodeMapError,
                                                     PathCombinationError)

from scholar_flux.utils.paths import PathSimplifier
from types import GeneratorType
from multiprocessing import Pool, cpu_count

from scholar_flux.utils.paths import ProcessingPath, PathNode
from scholar_flux.utils import is_nested
from scholar_flux.utils import try_quote_numeric, try_call
from weakref import WeakSet

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
                raise ValueError(f"The value provided to 'records' is invalid: No data to process.")

            current_path = current_path or ProcessingPath([],delimiter=self.DEFAULT_DELIMITER)
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
            raise

        except TypeError as e:
            logger.error(f"An unsupported type was encountered during path discovery: {e}")
            raise

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
        logger.debug(f'Cleared all paths from the Discoverer...')

class ProcessingCache:
    """
    A cache for storing Processing paths for faster prefix searches.
    """

    def __init__(self) -> None:
        """
        Initializes the ProcessingCache instance
        """

        self._cache: defaultdict[str, WeakSet[ProcessingPath]] = defaultdict(WeakSet) # Initialize the cache
        self.updates: dict[ProcessingPath, str] = {}

    def lazy_add(self, path: ProcessingPath) -> None:
        """
        Add a path to the cache for faster prefix searches.
        Args:
            path (ProcessingPath): The path to add to the cache.
        """
        if not isinstance(path, ProcessingPath):
            raise InvalidProcessingPathError(f'Path must be a ProcessingPath instance. Received: {path} - type={type(path)}')
        self.updates[path] = 'add'

    def lazy_remove(self, path: ProcessingPath) -> None:
        """
        Remove a path from the cache.
        Args:
            path (ProcessingPath): The path to remove from the cache.
        """

        if not isinstance(path, ProcessingPath):
            raise PathCacheError(f'path must be a ProcessingPath instance. Received: {path} - type={type(path)}')
        self.updates[path] = 'remove'

    def _add_to_cache(self, path: ProcessingPath) -> None:
        """
        Add a path to the cache for faster prefix searches.
        Args:
            path (ProcessingPath): The path to add to the cache.
        """
        if not isinstance(path, ProcessingPath):
            raise PathCacheError(f'path must be a ProcessingPath instance. Received: {path} - type={type(path)}')
        path_prefixes = path.get_ancestors() + [path]

        for path_prefix in path_prefixes:
            if path_prefix is None:
                raise ValueError(f'Invalid path prefix of type {type(path_prefix)}')
            self._cache[str(path_prefix)].add(path)
        logger.debug(f'Added path to cache: {path}')

    def _remove_from_cache(self, path: ProcessingPath) -> None:
        """
        Remove a path from the cache.
        Args:
            path (ProcessingPath): The path to remove from the cache.
        """
        if not isinstance(path,ProcessingPath):
            raise PathCacheError(f"Path Cache takes a ProcessingPath as input - received {type(path)}")

        path_prefixes = path.get_ancestors() + [path]
        for path_prefix in path_prefixes:
            if path_prefix is None:
                raise ValueError(f'Invalid path prefix of type {type(path_prefix)}')
            try:
                self._cache[str(path_prefix)].remove(path)
            except KeyError:
                logger.debug(f'Path not found in cache: {path}')
            else:
                logger.debug(f'Removed path from cache: {path}')

    def cache_update(self) -> None:
        """
        Initializes the lazy updates for the cache given the current update instructions.
        """
        for path, operation in self.updates.items():
            if operation == 'add':
                self._add_to_cache(path)
            elif operation == 'remove':
                self._remove_from_cache(path)
        self.updates.clear()

    def filter(self, prefix:  ProcessingPath,  min_depth: Optional[int] = None,  max_depth: Optional[int] = None) -> Set[ProcessingPath]:
        """
        Filter the cache for paths with the given prefix.
        Args:
            prefix (ProcessingPath): The prefix to search for.
            min_depth (Optional[int]): The minimum depth to search for. Default is None.
            max_depth (Optional[int]): The maximum depth to search for. Default is None.
        Returns:
            list[Optional[ProcessingPath]]: A list of paths with the given prefix.
        """
        self.cache_update()


        if not isinstance(prefix, (str,ProcessingPath)):
            raise InvalidProcessingPathError(f'Key must be a Processing Path. Received: {prefix} - type={type(prefix)}')

        if (min_depth is not None and min_depth < 0) or (max_depth is not None and max_depth < 1):
            raise ValueError(f'Minimum and Maximum depth must be None or greater than 0 or 1, respectively. Received: min={min_depth}, max={max_depth}')


        terminal_path_list  = {path for path in self._cache.get(str(prefix), set())
                               if path is not None and
                               (min_depth is None or min_depth <= path.depth) and
                               (max_depth is None or path.depth <= max_depth)}

        return terminal_path_list

class PathNodeMap(UserDict[ProcessingPath,PathNode]):
    """
    A dictionary-like class that maps Processing paths to PathNode objects.
    """
    def __init__(self,
                 *nodes: Union["PathNode",
                               Generator["PathNode", None, None],
                               tuple["PathNode"], list["PathNode"],
                               dict[str, "PathNode"],
                               dict[ProcessingPath, "PathNode"]],
                 cache: bool = True,
                 allow_terminal:Optional[bool] = False,
                 overwrite: Optional[bool] = True,
                 **path_nodes: dict[Union[str, ProcessingPath], "PathNode"]) -> None:
        """
        Initializes the PathNodeMap instance.
        """
        super().__init__()
        logger.debug('Initializing PathNodeMap instance')  # Log initialization
        self.cache: bool = cache or False  # Store the cache flag
        self.allow_terminal = allow_terminal or False,  # Store the allow_terminal flag
        self.overwrite: bool = overwrite or False  # Store the overwrite flag
        self._cache: ProcessingCache = ProcessingCache()

        if nodes or path_nodes:
            self.update(*nodes, **path_nodes,overwrite=self.overwrite)

    def __contains__(self, key: object) -> bool:
        """
        Checks if a key exists in the PathNodeMap instance.

        Args:
            key (Union[str, ProcessingPath]): The key (Processing path) to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """

        if isinstance(key, str):
            key = ProcessingPath.with_inferred_delimiter(key)
        if not isinstance(key,ProcessingPath):
            raise InvalidProcessingPathError("Unexpected value type observed: {type(key)}): Expected a ProcessingPath/string")
        return self.data.get(key) is not None


    def __setitem__(self,
                    key: ProcessingPath,
                    value: PathNode,
                    #*, overwrite: Optional[bool] = None
                   ) -> None:
        """
        Sets an item in the PathNodeMap instance.

        Args:
            key (ProcessingPath): The key (Processing path) to set.
            value (PathNode): The value (PathNode instance) to associate with the key.
            overwrite (bool): Flag indicating whether to overwrite the existing value if the key already exists.

        Raises:
            PathNodeMapError: If the key already exists and overwrite is False.
            InvalidPathNodeError: If the value is not a PathNode instance.
            InvalidProcessingPathError: If the key is not a ProcessingPath instance.
        """
        # Check if the key already exists and handle overwriting behavior
        key = self._validate_input(key,value,overwrite=self.overwrite)

        self._remove_nonterminal_nodes(value.path)
        super().__setitem__(key, value)

        if self.cache:
            self._cache.lazy_add(key)
        #self._add_to_cache(key)

    def __delitem__(self, key: Union[str,ProcessingPath]) -> None:
        """
        Deletes an item from the PathNodeMap instance.

        Args:
            key (ProcessingPath): The key (Processing path) to delete.

        Raises:
            PathNodeMapError: If the key does not exist in the PathNodeMap.
        """

        key = self._validate_path(key)
        if key not in self:
            raise PathNodeMapError(f'Key "{key}" not found in the PathNodeMap.')
        super().__delitem__(key)

        if self.cache:
            self._cache.lazy_remove(key)
        #self._remove_from_cache(key)

    def values(self):
        """enables looping over child/terminal nodes"""
        return self.data.values()

    def filter(self, prefix:  ProcessingPath,  min_depth: Optional[int] = None,  max_depth: Optional[int] = None, from_cache: Optional[bool]=None)-> dict[ProcessingPath, "PathNode"]:
        """
        Filter the PathNodeMap for paths with the given prefix.
        Args:
            prefix (ProcessingPath): The prefix to search for.
            min_depth (Optional[int]): The minimum depth to search for. Default is None.
            max_depth (Optional[int]): The maximum depth to search for. Default is None.
            from_cache (Optional[bool]): Whether to use cache when filtering based on a path prefix.
        Returns:
            dict[Optional[ProcessingPath], Optional[PathNode]]: A dictionary of paths with the given prefix and their corresponding
            terminal_nodes
        Raises:
            PathNodeMapError: If an error occurs while filtering the PathNodeMap.
        """
        use_cache = from_cache if from_cache is not None else self.cache
        try:
            terminal_nodes=self._cache_filter(prefix,min_depth,max_depth) if use_cache else self._filter(prefix,min_depth,max_depth)
            return terminal_nodes

        except Exception as e:
            raise PathNodeMapError(f'Error filtering paths with prefix {prefix}:') from e

    def _filter(self, prefix:  ProcessingPath,  min_depth: Optional[int] = None,  max_depth: Optional[int] = None)-> dict[ProcessingPath, "PathNode"]:
        """
        Filter the PathNodeMap for paths with the given prefix.
        Args:
            prefix (ProcessingPath): The prefix to search for.
            min_depth (Optional[int]): The minimum depth to search for. Default is None.
            max_depth (Optional[int]): The maximum depth to search for. Default is None.
            from_cache (Optional[int]): Whether to use cache when filtering based on a path prefix.
        Returns:
            dict[Optional[ProcessingPath], Optional[PathNode]]: A dictionary of paths with the given prefix and their corresponding
            terminal_nodes
        Raises:
            PathNodeMapError: If an error occurs while filtering the PathNodeMap.
        """
        try:
            if (min_depth is not None and min_depth < 0) or (max_depth is not None and max_depth < 1):
                raise ValueError(f'Minimum and Maximum depth must be None or greater than 0 or 1, respectively. Received: min={min_depth}, max={max_depth}')

            if not isinstance(prefix, (str,ProcessingPath)):
                raise InvalidProcessingPathError(f'Key must be a ProcessingPath. Received: {prefix} - type={type(prefix)}')

            terminal_node_list  = {path:node for path,node in self.data.items()
                                   if (min_depth is None or min_depth <= path.depth) and
                                      (max_depth is None or path.depth <= max_depth) and
                                      path.has_ancestor(prefix) or path == prefix
                                  }

            return terminal_node_list

        except Exception as e:
            raise PathNodeMapError(f'Error filtering paths with prefix {prefix} at max_depth {max_depth}') from e

    def _remove_nonterminal_nodes(self, path: ProcessingPath)-> None:
            """
            Filter the PathNodeMap for paths with the given prefix.
            Args:
                path (ProcessingPath): The prefix to search for.
                from_cache (Optional[int]): Whether to use cache when filtering based on a path prefix.
            Returns:
                dict[Optional[ProcessingPath], Optional[PathNode]]: A dictionary of paths with the given prefix and their corresponding
                terminal_nodes
            Raises:
                PathNodeMapError: If an error occurs while filtering the PathNodeMap.
            """
            try:
                path_ancestors =  path.get_ancestors()
                if removed_nodes:= [ancestor_path for ancestor_path in path_ancestors if ancestor_path is not None and self.data.pop(ancestor_path,None) is not None]:
                    logger.debug(f'Removed {len(removed_nodes)} nodes that are no longer terminal: {removed_nodes}')
            except Exception as e:
                raise PathNodeMapError(f'Error searching for and removing ancestor paths for the path: {path}') from e


    def _cache_filter(self, prefix:  ProcessingPath,  min_depth: Optional[int] = None,  max_depth: Optional[int] = None)-> dict[ProcessingPath,"PathNode"]:
        """
        Use the enabled cache to filter the PathNodeMap for paths with the given prefix.
        Args:
            prefix (ProcessingPath): The prefix to search for.
            min_depth (Optional[int]): The minimum depth to search for. Default is None.
            max_depth (Optional[int]): The maximum depth to search for. Default is None.
        Returns:
            dict[Optional[ProcessingPath], Optional[PathNode]]: A dictionary of paths with the given prefix and their corresponding
            terminal_nodes
        Raises:
            PathNodeMapError: If an error occurs while filtering the PathNodeMap.
        """

        try:
            if not self.cache:
                raise PathNodeMapError('Cannot filter without cache. Please enable cache during initialization.')


            terminal_node_list = self._cache.filter(prefix,min_depth=min_depth,max_depth=max_depth)
            terminal_nodes =  {path: self.data[path] for path in terminal_node_list}
            return terminal_nodes
        except Exception as e:
            raise PathNodeMapError(f'Error filtering paths with prefix {prefix} at max_depth {max_depth}') from e


    def _validate_key_value_pair(self, processing_path: ProcessingPath, node: "PathNode") -> None:
        """
        Validate the current key-value pair of the node and path being used as a key within the PathNodeMap.
        Validates in terms of data integrity: name of key if provided matches name of node.path
        name [last component] = node.path [last component]

        Args:
            processing_path (ProcessingPath): The ProcessingPath instance to compare against the current path already associated with the PathNode.
            node (PathNode): The PathNode instance containing the full path to compare.

        Raises:
            PathNodeMapError: If the equal name/complete path constraint is violated.
        """
        if not isinstance(processing_path,ProcessingPath):
            raise PathNodeMapError(f'Invalid path path: {processing_path}. Must be a ProcessingPath instance.')

        if processing_path.depth == 1:
            if  processing_path.get_name() != node.path.get_name():
                raise PathNodeMapError(f'Invalid path path name: The name of the current node {processing_path} does not match the name of the last component of the path within the provided node: {node})')

        # Check if the processing_path matches the node's full path exactly
        elif processing_path != node.path:
            raise PathNodeMapError(f'Invalid path: The key provided as a path:  {processing_path}  does not match the path within the provided node: {node}')

        # Prevent reassigning paths to the same path map
        #if processing_path in self and self[processing_path] is not node:
        #    raise PathNodeMapError(f'Non-unique path: {processing_path}. Reassigning paths to the same map is not allowed.')

        if descendant_nodes := self.filter(node.path,min_depth=node.path.depth+1):
            raise PathNodeMapError(f'Unable to insert node at path ({node.path}): There are a total of {len(descendant_nodes)} nodes containing the path of the current node as a prefix.')

    def node_exists(self, node: Union["PathNode",ProcessingPath]) -> bool:
        if not isinstance(node, (PathNode, ProcessingPath)):
            raise KeyError(f"Key must be node or path. Received '{type(node)}'")

        if isinstance(node,PathNode):
            node = node.path

        return self.data.get(node) is not None

    def _validate_new_node_path(self, node: Union["PathNode",ProcessingPath],overwrite:Optional[bool]=None):
        overwrite = overwrite if overwrite is not None else self.overwrite
        if self.node_exists(node):
            if not overwrite:
                raise PathNodeMapError(f"A path and node at '{node}' already exists in the Map")
            else:
                logger.debug(f"The node at '{node}' will be ovewritten")

    def _validate_node(self, node: "PathNode", overwrite: Optional[bool] = None):
        """
        Validate constraints on the node to be inserted into the PathNodeMap.

        Args:
            node (PathNode): The PathNode instance to validate.

        Raises:
            PathNodeMapError: If any constraint is violated.
        """

        try:

            PathNode.is_valid_node(node)
            self._validate_new_node_path(node, overwrite=overwrite)

            logger.debug(f'Validated node: {node}')


        except Exception as e:
            raise PathNodeMapError(f'Error validating constraints on node insertion: {e}') from e

    @classmethod
    def _keep_terminal_paths(cls,path_list:Union[list[ProcessingPath],Set[ProcessingPath],Generator[ProcessingPath,None,None]]) -> Set[ProcessingPath]:
        """
        Filter a list of paths to keep only terminal paths.
        Args:
            path_list (list[ProcessingPath]): The list of paths to filter.
            Returns:
                Set[ProcessingPath]: A set of terminal paths.
        """
        sorted_path_list = sorted(path_list, key=lambda path: path._to_alphanum(depth_first = True), reverse=True)
        if not sorted_path_list:
            return set()
        max_depth = sorted_path_list[0].depth
        filtered_path_list = set()
        all_prefixes = set()

        for path in sorted_path_list:
            if path.depth == max_depth:
                filtered_path_list.add(path)
                continue
            # Check if path is already a known prefix
            if path in all_prefixes:
                logger.warning(f"The path '{path}' is non-terminal in the list of node to add. Removing...")
                continue

            if path in filtered_path_list:
                logger.warning(f"The path '{path}' is duplicated. Removing and retaining the last inputted entry...")
                continue

            # If not, add it to the filtered_path_list
            filtered_path_list.add(path)

            # Add all prefixes of this string to the set
            all_prefixes.update(path.get_ancestors())

        return filtered_path_list

    @classmethod
    def format_terminal_nodes(cls,node_obj:Union[dict,PathNodeMap,PathNode])-> dict[ProcessingPath, "PathNode"]:
        """
        Recursively iterate over terminal nodes from Path Node Maps and retrieve only terminal_nodes
        Args:
            node_obj (Union[dict,PathNodeMap]): PathNode map or node dictionary containing either nested or already flattened terminal_paths
        Returns:
            item (dict): the flattened terminal paths extracted from the inputted node_obj
        """

        if isinstance(node_obj,PathNodeMap):
            return node_obj.data

        if isinstance(node_obj, dict):
            return {path:node for path, node in node_obj.items()
                    if PathNode.is_valid_node(node) and isinstance(path, ProcessingPath)}

        if isinstance(node_obj, PathNode):
            return {node_obj.path: node_obj}

        raise ValueError(f'Invalid input to node_obj: argument must be a Path Node Map or a PathNode. Received ({type(node_obj)})')


    @staticmethod
    def _transform_key(key: Union[str,ProcessingPath],delimiter: str) -> ProcessingPath:
        """For coercing string type keys into ProcessingPaths if not already path types
        Args:
            path (Union[str, list[str]]): The initial path, either as a string or a list of strings.
            delimiter (str): The delimiter used to separate components in the path.
        Returns:
            ProcessingPath: the path leading to the node that this object corresponds to
            """
        if not isinstance(key,ProcessingPath):
            transformed_key = ProcessingPath.to_processing_path(key,component_types=None,delimiter=delimiter)
            if not key is transformed_key:
                logger.debug(f'converted {key} --> {transformed_key}')
            return transformed_key
        return key

    def _validate_input(self, path: Union[str,ProcessingPath], node: "PathNode",overwrite: Optional[bool] = None) -> ProcessingPath:
        """
        Method of performing key-value pair validation while returning the path if the pair is valid:

        Args:
            path (Union[str, ProcessingPath]): The initial path, formatted as a string or a ProcessingPath instance.
            node (PathNode): The PathNode instance to validate.
        Returns:
            ProcessingPath: A ProcessingPath instance.

        Raises:
            PathNodeMapError If the path object, node path is invalid, or combination of the key and node pair is invalid.
        """
        try:
            self._validate_node(node,overwrite)
            transformed_path=self._transform_key(path,delimiter=node.path.delimiter)
            self._validate_key_value_pair(transformed_path,node)
            return transformed_path
        except Exception as e:
            raise PathNodeMapError(f'Error validating path ({path}) and node ({node}): {e}') from e

    def format_mapping(self, key_value_pairs: Union['PathNodeMap',dict[ProcessingPath, "PathNode"],dict[str, "PathNode"]]) -> dict[ProcessingPath, "PathNode"]:
        """
        Takes a dictionary or a PathNodeMap Transforms the string keys in a dictionary into Processing paths and returns the mapping

        Args:
            key_value_pairs (Union[dict[ProcessingPath, PathNode], dict[str, PathNode]]): The dictionary of key-value pairs to transform.
        Returns:
            dict[ProcessingPath, PathNode]: a dictionary of validated path, node pairings
        Raises:
            PathNodeMapError: If the validation process fails.
        """
        try:
            terminal_nodes = self.format_terminal_nodes(key_value_pairs)
            if len(terminal_nodes)==0:
                return terminal_nodes
            terminal_paths = self._keep_terminal_paths(set(node.path for node in terminal_nodes.values()))
            filtered_dict = {path:node for path, node in terminal_nodes.items() if path in terminal_paths}
        except Exception as e:
            raise PathNodeMapError(f':The validation process for the input pairs failed: {e}')

        return filtered_dict

    def _extract_node(self,*nodes) -> Optional['PathNode']:
        """
            Attempts to extract a node from arguments of arbitrary lengths.
            If there is more than one node, this method will return None with
            the aim of defering processing multiple nodes to other helper methods

        """
        if isinstance(nodes,PathNode):
            return nodes

        if isinstance(nodes,(list,tuple)) and len(nodes) == 1:
            node=nodes[0]
            return node if isinstance(node,PathNode) else None
        return None

    def _format_nodes_as_dict(self,*nodes,**path_nodes) -> Union['PathNodeMap',dict[ProcessingPath, "PathNode"],dict[ProcessingPath, "PathNode"]]:
        """
        Helper function to format the input arguments as a dictionary.
        """

        type_verified = False
        node_dict =self.format_mapping(path_nodes)

        if not nodes:
            return node_dict

        formatted_nodes: tuple | dict | list | set | Generator = (
            nodes[0] if (isinstance(nodes,tuple) and len(nodes) == 1 and \
                         not isinstance(nodes[0],PathNode)) \
            else  nodes
        )

        if isinstance(formatted_nodes, (tuple,list, set,GeneratorType)):
            processed_nodes = {node.path:node for node in formatted_nodes if PathNode.is_valid_node(node)}
            type_verified = True
        else:
            processed_nodes = formatted_nodes if isinstance(formatted_nodes, dict) else {}




        if isinstance(processed_nodes, (dict,PathNodeMap)):
            if processed_nodes:
                if not type_verified and not isinstance(processed_nodes,PathNodeMap) and not all(isinstance(node,PathNode) for node in processed_nodes.values()):
                    raise InvalidPathNodeError(f'Invalid node type: {type(nodes)}. Must be a PathNode or an iterable of PathNodes.')

                node_dict=node_dict | self.format_mapping(processed_nodes)
        else:
            raise InvalidPathNodeError(f'Invalid node type: {type(nodes)}. Must be a PathNode or an iterable of PathNodes.')
        return node_dict



    def update(self, # type: ignore[override]
               *args,
               overwrite:Optional[bool]=None,
               **kwargs: dict[Union[str,ProcessingPath], "PathNode"])->None:
        """
        Updates the PathNodeMap instance with new key-value pairs.

        Args:
            *args (Union["PathNodeMap",dict[ProcessingPath, PathNode],dict[str, PathNode]]): PathNodeMap or dictionary containing the key-value pairs to append to the PathNodeMap
            overwrite (bool): Flag indicating whether to overwrite existing values if the key already exists.
            *kwargs (PathNode): Path Nodes using the path as the argument name to append to the PathNodeMap
        Returns
        """
        logger.debug('Updating PathNodeMap instance')  # Log updating
        default_overwrite = self.overwrite
        overwrite=overwrite if overwrite is not None else default_overwrite
        #kwargs = {key:node for key,node in kwargs.items() if isinstance(node,PathNode)}

        # if there is only one node to extract
        node=self._extract_node(*args) if not kwargs else None
        if node:
            try:
                self.overwrite = overwrite
                self.__setitem__(node.path, node)
            except Exception as e:
                raise PathNodeMapError(f"An error occurred during updating: {e}") from e
            finally:
                self.overwrite = default_overwrite

            return


        node_dict = self._format_nodes_as_dict(*args,**kwargs)

        try:
            # setting and using self.overwrite as a tempoary overwrite parameter
            self.overwrite = overwrite
            super().update(node_dict)
        except Exception as e:
            raise PathNodeMapError(f"An error occurred during updating: {e}") from e
        finally:
            self.overwrite = default_overwrite

        logger.debug("Updated successfully")

    def get( # type: ignore[override]
            self,
            key: Union[str,ProcessingPath],
            default:Optional[PathNode]=None
           )->Optional[PathNode]:
        """
        Gets an item from the PathNodeMap instance. If the value isn't available,
        this method will return the value specified in default

        Args:
            key (Union[str,ProcessingPath]): The key (Processing path) If string, coerces to a ProcessingPath.

        Returns:
            PathNode: The value (PathNode instance).
        """

        key = self._validate_path(key)
        return super().get(key)


    def __getitem__(self, key: Union[str,ProcessingPath]) -> PathNode:
        """
        Gets an item from the PathNodeMap instance.

        Args:
            key (Union[str,ProcessingPath]): The key (Processing path) If string, coerces to a ProcessingPath.
        Returns:
            PathNode: The value (PathNode instance).
        """
        key = self._validate_path(key)
        return self.data[key]

    @staticmethod
    def _validate_path(key: object) -> ProcessingPath:
        """
        For coercing strings into processing paths if the object is not already a path
        Args:
            key (Union[str,ProcessingPath]): A path object in string/ProcessingPath
                                             for retrieving, searching, deleting objects, etc.
        Returns:
            ProcessingPath: Returns the path as is if a ProcessingPath. otherwise
                            this method coerces string inputs into a ProcesingPath

        Raises:
            InvalidProcessingPathError if the value is anything other than a string/path object already
        """
        if isinstance(key, str):
            key = ProcessingPath.with_inferred_delimiter(key)
        if not isinstance(key,ProcessingPath):
            raise InvalidProcessingPathError(f"Unexpected value type observed: {type(key)}): Expected a ProcessingPath/string")
        return key

    def add(self, node: "PathNode", overwrite: Optional[bool] = None, inplace:bool = True) -> Optional['PathNodeMap']:
        """
        Add a node to the PathNodeMap instance.

        Args:
            node (PathNode): The node to add.
            overwrite (bool): Flag indicating whether to overwrite existing values if the key already exists.

        Raises:
            PathNodeMapError: If any error occurs while adding the node.
        """

        default_overwrite = self.overwrite
        try:
            if not inplace:
                path_node_map=copy.deepcopy(self)
                path_node_map.add(node,
                                  overwrite=overwrite,
                                  inplace=True)
                return path_node_map
            if PathNode.is_valid_node(node):
                logger.debug(f"Adding node: '{node}'")
            self.__setitem__(node.path,node,
                             # overwrite=overwrite
                            )
        except Exception as e:
            raise PathNodeMapError(f'Error adding nodes to PathNodeMap: {e}') from e
        finally:
            self.overwrite = default_overwrite
        return None

    def remove(self, node:Union[ProcessingPath, "PathNode", str],inplace:bool=True) -> Optional['PathNodeMap']:
        """
        Remove the specified path or node from the PathNodeMap instance.
        Args:
            node (Union[ProcessingPath, PathNode, str]): The path or node to remove.
            inplace (bool): Whether to remove the path in-place or return a new PathNodeMap instance. Default is True.

        Returns:
            Optional[PathNodeMap]: A new PathNodeMap instance with the specified paths removed if inplace is specified as True.

        Raises:
            PathNodeMapError: If any error occurs while removing.
        """
        try:
            if not inplace:
                path_node_map=copy.deepcopy(self)
                path_node_map.remove(node, inplace=False)
                return path_node_map

            if not isinstance(node, (str, ProcessingPath,PathNode)):
                raise PathNodeMapError(f'Invalid type for node: {type(node)}. Must be a ProcessingPath or a PathNode.')

            path = node.path if isinstance(node, PathNode) else ProcessingPath.to_processing_path(node)

            logger.debug(f"Removing node: '{node}'")
            del self.data[path]

        except Exception as e:
            raise PathNodeMapError(f'Error removing paths from PathNodeMap: {e}') from e
        return None

    def __copy__(self) -> 'PathNodeMap':
        """
        Create a copy of the current path-node combinations and their contents.

        Returns:
            SparsePathNodeMap: A new map of path-node combinations  with the same attributes
            and values as the current map.
        """
        try:
            path_node_map = self.__class__()
            path_node_map.__dict__ = self.__dict__.copy()
            return path_node_map

        except Exception as e:

            logger.exception(f'Error copying map "{self}": {e}')
            raise PathNodeMapError(f'Error copying map: {e}')



@dataclass
class PathNodeIndex:
    DEFAULT_DELIMITER: ClassVar[str] = ProcessingPath.DEFAULT_DELIMITER
    index: PathNodeMap = field(default_factory=PathNodeMap)
    simplifier: PathSimplifier = field(
        default_factory=lambda: PathSimplifier(delimiter=PathNodeIndex.DEFAULT_DELIMITER,
                                               non_informative=['i','value'])
    )

    def __post_init__(self):
        object.__setattr__(self, 'index', self._validate_index(self.index))
        object.__setattr__(self, 'simplifier', self._validate_simplifier(self.simplifier))

    @classmethod
    def _validate_simplifier(cls,simplifier: PathSimplifier)->PathSimplifier:
        """
        Determine whether the argument provided to the simplifier parameter
        Is of type PathSimplifier.
        Args:
            simplifier (PathSimplifier): A simplifier object for normalizing records
        Raises:
            PathNodeIndexError in the event that the expected type is not a PathSimplifier
        """
        if not isinstance(simplifier,PathSimplifier):
            raise PathNodeIndexError(f"The argument, simplifier, expected a PathSimplifier. Recieved {type(simplifier)}")
        return simplifier

    @classmethod
    def _validate_index(cls,index: Union[PathNodeMap,dict[ProcessingPath, PathNode]])->PathNodeMap:
        """
        Determine whether the current path is an index of paths and nodes.
        Args:
            index (dict[ProcessingPath, PathNode])
        Raises:
            PathNodeIndexError in the event that the expected type is not a dictionary of paths
        """
        if isinstance(index, dict):
            return PathNodeMap(index)
        if not isinstance(index, PathNodeMap):
            raise PathNodeIndexError(f"The argument, index, expected a PathNodeMap. Recieved {type(index)}")
        return index


    @classmethod
    def from_path_mappings(cls, path_mappings: dict[ProcessingPath, Any])->PathNodeIndex:
        """
        Takes a dictionary of path:value mappings and transforms the dictionary into
        a list of PathNodes: useful for later path manipulations such as grouping and
        consolidating paths into a flattened dictionary.

        Returns:
            list[PathNode]: list of pathnodes created from a dictionary
        """

        return cls(PathNodeMap({path:PathNode(path,value) for path, value in path_mappings.items()}))

    def __repr__(self)->str:
        return f"PathNodeIndex(index(len={len(self.index)})"

    def retrieve(self, path: Union[ProcessingPath, str]) -> Optional[PathNode]:
        """
        Try to retrieve a path node with the given path.

        Args:
            The exact path of to search for in the index
        Returns:
            Optional[PathNode]: The exact node that matches the provided path.
                                Returns None if a match is not found
        """
        return self.index.get(path)

    def search(self, path: ProcessingPath) -> list[PathNode]:
        """
        Attempt to find all values with that match the provided path or have sub-paths
        that are an exact match match to the provided path
        Args:
            path Union[str, ProcessingPath] the path to search for.
            Note that the provided path must match a prefix/ancestor path of an indexed path
            exactly to be considered a match
        Returns:
            dict[PrcoessingPath, PathNode]: All paths equal to or containing sub-paths
                                            exactly matching the specified path
        """
        return [node for node in self.index.filter(path).values()]

    def pattern_search(self, pattern: Union[str, re.Pattern]) -> list[PathNode]:
        """Attempt to find all values containing the specified pattern using regular expressions
        Args:
            pattern (Union[str, re.Pattern]) pattern to search for
        Returns:
            dict[PrcoessingPath, PathNode]: all paths and nodes that match the specified pattern
        """

        if not isinstance(pattern, (str,re.Pattern)):
            raise TypeError("Invalid Value passed to PathIndex: expected string/re.Pattern, received ({type(pattern)})")
        pattern = re.compile(pattern) if not isinstance(pattern,re.Pattern) else pattern
        return [node for node in self.index.values() if pattern.search(node.path.to_string()) is not None]

    def simplify_to_rows(self, object_delimiter: Optional[str] = ';', parallel: bool = False) -> list[dict[str,Any]]:
        """
        Simplify indexed nodes into a paginated data structure.
        Args:
            object_delimiter (str): The separator to use when collapsing multiple values into a single string.
            parallel (bool): Whether or not the simplification into a flattened structure should occur in parallel
        Returns:
            list[dict[str, Any]]: A list of dictionaries representing the paginated data structure.
        """
        sorted_nodes=sorted(self.index.values(),
                            key=lambda node: (node.path_keys, node.path))

        self.simplifier.simplify_paths([node.path_group for node in sorted_nodes],
                                       max_components=3,remove_noninformative=True)

        indexed_nodes = defaultdict(set)

        for node in sorted_nodes:
            indexed_nodes[node.record_index].add(node)

        # Prepare data for multiprocessing
        node_chunks = [(node_chunk,) for node_chunk in indexed_nodes.values()]

        if not parallel:
            return [self.simplifier.simplify_to_row(indexed_nodes[idx],collapse=object_delimiter) for idx in indexed_nodes.keys()]

        # Use multiprocessing to process nodes in parallel
        with Pool(processes=max(cpu_count(), len(node_chunks))) as pool:
            normalized_rows = pool.starmap(self.simplifier.simplify_to_row, node_chunks)
        return normalized_rows


        #return [self.simplifier.simplify_to_row(indexed_nodes[idx],collapse=object_delimiter) for idx in indexed_nodes.keys()]

    def combine_keys(self,skip_keys: Optional[list] = None) -> None:
            """
            Combine nodes with values in their paths by updating the paths of count nodes.

            This method searches for paths ending with values and count, identifies related nodes,
            and updates the paths by combining the value with the count node.

            Args:
                skip_keys (Optional[list]): Keys that should not be combined regardless of a matching pattern
                quote_numeric (Optional[bool]): Determines whether to quote integer components of paths to distinguish from Indices (default behavior is to quote them (ex. 0, 123).


            Raises:
                PathCombinationError: If an error occurs during the combination process.
            """
            try:
                skip_keys = skip_keys or []

                # Search for paths ending with 'values' and 'count'
                count_node_list = self.pattern_search(re.compile(r'.*value(s)?.*count$'))
                node_updates = 0

                for count_node in count_node_list:
                    if count_node is None or count_node.path in skip_keys:
                        logger.debug(f'Skip keys include \'{count_node.path}\'. Continuing...')
                        continue
                    #try:
                    if not count_node.path.depth > 1:
                        logger.debug(f'Skipping node \'{count_node}\' at depth={count_node.path.depth} as it cannot be combined.')
                        continue

                   # Search for value nodes related to the count node
                    value_node_pattern = (count_node.path[:-1] / 'value$').to_pattern()
                    value_node_list = self.pattern_search(value_node_pattern)

                    if len(value_node_list) == 1:
                        value_node = value_node_list[0]

                        if value_node is None:
                            logger.debug(f'Value is None for {value_node}. Continuing...')
                            continue

                        value = try_quote_numeric(value_node.value) or value_node.value
                        if value is None:
                            logger.debug(f'Value is None for {value_node} Continuing...')
                            continue

                        # Create new path for the combined node
                        updated_count_path = (
                            value_node.path /
                             value /
                            'count'
                        )

                        # Update the count node path
                        updated_count_node = count_node.update(path=updated_count_path)
                        self.index.add(updated_count_node, overwrite=True)
                        try_call(self.index.remove,
                                 args=(value_node,),
                                 suppress=(PathNodeMapError,),
                                 log_level=logging.INFO)

                        try_call(self.index.remove,
                                 args=(count_node,),
                                 suppress=(PathNodeMapError,),
                                 log_level=logging.INFO)

                        # avoid attempting to add combine newly combined nodes to prevent redundancy
                        skip_keys.append(count_node)

                        # Remove the old value node
                        #self.remove(value_node)
                        node_updates += 1

                logger.info(f'Combination of {node_updates} nodes successful' if node_updates > 0 else 'No combinations of nodes were performed')

            except Exception as e:
                logger.exception(f'Error during key combination: {e}')
                raise PathCombinationError(f'Error during key combination: {e}')

    @classmethod
    def normalize_records(cls,
                          json_records: dict | list[dict],
                          combine_keys: bool = True,
                          object_delimiter: Optional[str] = ';',
                          parallel: bool = False) -> list[dict[str,Any]]:
        """
        Full pipeline for processing a loaded JSON structure into a list of dictionaries where
        each individual list element is a processed and normalized record.
        Args:
            json_records (dict[str,Any] | list[dict[str,Any]]): The JSON structure to normalize. If this structure
                         is a dictionary, it will first be nested in a list as a single element before processing.
            combine_keys: bool: This function determines whetehr or not to combine keys that are likely to
                                denote names and corresponding values/counts. Default is True
            object_delimiter: This delimiter determines whether to join terminal paths in lists under the same key
                              and how to collapse the list into a singular string. If empty, terminal lists
                              are returned as is.
            parallel (bool): Whether or not the simplification into a flattened structure should occur in parallel
        Returns:
            list[dict[str,Any]]:
        """

        if not isinstance(json_records, (dict, list)):
            raise PathNodeIndexError(f"Normalization requires a list or dictionary. Received {type(json_records)}")

        record_list = json_records if isinstance(json_records, list) else [json_records]
        path_mappings=PathDiscoverer(json_records).discover_path_elements() if isinstance(json_records,list) else {}


        if not isinstance(path_mappings, dict) or not path_mappings:
            logger.warning("The json structure of type, {type(json_records)} contains no rows. Returning an empty list")
            return []

        logger.info(f"Discovered {len(path_mappings)} terminal paths")
        path_node_index = cls.from_path_mappings(path_mappings)
        logger.info(f"Created path index succesfully from the provided path mappings")
        if combine_keys:
            logger.info("Combining keys..")
            path_node_index.combine_keys()
        normalized_records = path_node_index.simplify_to_rows(object_delimiter=object_delimiter,parallel=parallel)
        logger.info("Successfully noralized {len(normalized_records)} records")
        return normalized_records
