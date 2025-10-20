# /utils/paths/path_node_map.py
"""The scholar_flux.utils.paths.path_node_map module implements the PathNodeMap that is used to record terminal path-
value combinations that enables more efficient mapping, retrieval, and updates to terminal path node combinations."""
from __future__ import annotations

import copy
from typing import Optional, Union, Set, Generator, MutableMapping, Mapping, Sequence
from collections import UserDict
from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    PathNodeMapError,
)

from types import GeneratorType

from scholar_flux.utils.paths import ProcessingPath, PathNode, PathProcessingCache
from scholar_flux.utils import unlist_1d

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class PathNodeMap(UserDict[ProcessingPath, PathNode]):
    """A dictionary-like class that maps Processing paths to PathNode objects."""

    DEFAULT_USE_CACHE: bool = True

    def __init__(
        self,
        *nodes: Union[
            PathNode,
            Generator[PathNode, None, None],
            tuple[PathNode],
            list[PathNode],
            set[PathNode],
            dict[str, PathNode],
            dict[ProcessingPath, PathNode],
        ],
        use_cache: Optional[bool] = None,
        allow_terminal: Optional[bool] = False,
        overwrite: Optional[bool] = True,
        **path_nodes: Mapping[str | ProcessingPath, PathNode],
    ) -> None:
        """Initializes the PathNodeMap instance."""
        super().__init__()
        logger.debug("Initializing PathNodeMap instance")  # Log initialization
        self.use_cache: bool = use_cache if use_cache is not None else self.DEFAULT_USE_CACHE  # Store the cache flag
        self.allow_terminal = (allow_terminal or False,)  # Store the allow_terminal flag
        self.overwrite: bool = overwrite or False  # Store the overwrite flag
        self._cache: PathProcessingCache = PathProcessingCache()

        if nodes or path_nodes:
            self.update(*nodes, **path_nodes, overwrite=self.overwrite)

    def __contains__(self, key: object) -> bool:
        """Checks if a key exists in the PathNodeMap instance.

        Args:
            key (Union[str, ProcessingPath, PathNode]): The key that is, or contains, a Processing path to check.

        Returns:
            bool: True if the key exists, False otherwise.

        """
        if key is None:
            return False

        if isinstance(key, PathNode):
            key = key.path
        if isinstance(key, str):
            key = ProcessingPath.with_inferred_delimiter(key)
        if not isinstance(key, ProcessingPath):
            raise InvalidProcessingPathError(
                f"Unexpected value type observed: {type(key)}: Expected a ProcessingPath/string"
            )
        return self.data.get(key) is not None

    def __setitem__(
        self,
        key: ProcessingPath,
        value: PathNode,
        # *, overwrite: Optional[bool] = None
    ) -> None:
        """Sets an item in the PathNodeMap instance.

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
        key = self._validate_input(key, value, overwrite=self.overwrite)

        self._remove_nonterminal_nodes(value.path)
        super().__setitem__(key, value)

        if self.use_cache:
            self._cache.lazy_add(key)
        # self._add_to_cache(key)

    def __delitem__(self, key: Union[str, ProcessingPath]) -> None:
        """Deletes an item from the PathNodeMap instance.

        Args:
            key (ProcessingPath): The key (Processing path) to delete.

        Raises:
            PathNodeMapError: If the key does not exist in the PathNodeMap.

        """

        key = self._validate_path(key)
        if key not in self:
            raise PathNodeMapError(f'Key "{key}" not found in the PathNodeMap.')
        super().__delitem__(key)

        if self.use_cache:
            self._cache.lazy_remove(key)

    @property
    def nodes(self) -> list[PathNode]:
        """Enables the retrieval of paths stored within the current map as a property."""
        return list(self.data.values())

    @property
    def paths(self) -> list[ProcessingPath]:
        """Enables retrieval of nodes stored within the current map as a property."""
        return list(self.data.keys())

    def filter(
        self,
        prefix: ProcessingPath | str | int,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
        from_cache: Optional[bool] = None,
    ) -> dict[ProcessingPath, PathNode]:
        """Filter the PathNodeMap for paths with the given prefix.

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
        use_cache = from_cache if from_cache is not None else self.use_cache
        prefix = ProcessingPath.to_processing_path(prefix) if not isinstance(prefix, ProcessingPath) else prefix
        try:
            terminal_nodes = (
                self._cache_filter(prefix, min_depth, max_depth)
                if use_cache
                else self._filter(prefix, min_depth, max_depth)
            )
            return terminal_nodes

        except Exception as e:
            raise PathNodeMapError(f"Error filtering paths with prefix {prefix}: {e}") from e

    def _filter(
        self,
        prefix: ProcessingPath,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> dict[ProcessingPath, PathNode]:
        """Filter the PathNodeMap for paths with the given prefix.

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
                raise ValueError(
                    f"Minimum and Maximum depth must be None or greater than 0 or 1, respectively. Received: min={min_depth}, max={max_depth}"
                )

            if not isinstance(prefix, (str, ProcessingPath)):
                raise InvalidProcessingPathError(
                    f"Key must be a ProcessingPath. Received: {prefix} - type={type(prefix)}"
                )

            terminal_node_list = {
                path: node
                for path, node in self.data.items()
                if (min_depth is None or min_depth <= path.depth)
                and (max_depth is None or path.depth <= max_depth)
                and path.has_ancestor(prefix)
                or path == prefix
            }

            return terminal_node_list

        except Exception as e:
            raise PathNodeMapError(f"Error filtering paths with prefix {prefix} at max_depth {max_depth}") from e

    def _remove_nonterminal_nodes(self, path: ProcessingPath) -> None:
        """Filter the PathNodeMap for paths with the given prefix.

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
            path_ancestors = path.get_ancestors()
            if removed_nodes := [
                ancestor_path
                for ancestor_path in path_ancestors
                if ancestor_path is not None and self.data.pop(ancestor_path, None) is not None
            ]:
                logger.debug(f"Removed {len(removed_nodes)} nodes that are no longer terminal: {removed_nodes}")
        except Exception as e:
            raise PathNodeMapError(f"Error searching for and removing ancestor paths for the path: {path}") from e

    def _cache_filter(
        self,
        prefix: ProcessingPath,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> dict[ProcessingPath, PathNode]:
        """Use the enabled cache to filter the PathNodeMap for paths with the given prefix.

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
            if not self.use_cache:
                raise PathNodeMapError("Cannot filter without cache. Please enable cache during initialization.")

            terminal_node_list = self._cache.filter(prefix, min_depth=min_depth, max_depth=max_depth)
            terminal_nodes = {path: self.data[path] for path in terminal_node_list}
            return terminal_nodes
        except Exception as e:
            raise PathNodeMapError(f"Error filtering paths with prefix {prefix} at max_depth {max_depth}: {e}") from e

    def _validate_key_value_pair(self, processing_path: ProcessingPath, node: PathNode) -> None:
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
        if not isinstance(processing_path, ProcessingPath):
            raise PathNodeMapError(f"Invalid path path: {processing_path}. Must be a ProcessingPath instance.")

        if processing_path.depth == 1:
            if processing_path.get_name() != node.path.get_name():
                raise PathNodeMapError(
                    f"Invalid path path name: The name of the current node {processing_path} does not match the name of the last component of the path within the provided node: {node})"
                )

        # Check if the processing_path matches the node's full path exactly
        elif processing_path != node.path:
            raise PathNodeMapError(
                f"Invalid path: The key provided as a path:  {processing_path}  does not match the path within the provided node: {node}"
            )

        # Prevent reassigning paths to the same path map
        # if processing_path in self and self[processing_path] is not node:
        #    raise PathNodeMapError(f'Non-unique path: {processing_path}. Reassigning paths to the same map is not allowed.')

        if descendant_nodes := self.filter(node.path, min_depth=node.path.depth + 1):
            raise PathNodeMapError(
                f"Unable to insert node at path ({node.path}): There are a total of {len(descendant_nodes)} nodes containing the path of the current node as a prefix."
            )

    def node_exists(self, node: Union[PathNode, ProcessingPath]) -> bool:
        """Helper method to validate whether the current node exists."""
        if not isinstance(node, (PathNode, ProcessingPath)):
            raise KeyError(f"Key must be node or path. Received '{type(node)}'")

        if isinstance(node, PathNode):
            node = node.path

        return self.data.get(node) is not None

    def _validate_new_node_path(self, node: Union[PathNode, ProcessingPath], overwrite: Optional[bool] = None):
        """Helper method to validate whether the current node already exists in the current map: Raises an error if the
        field does.

        otherwise, if overwriting is enabled, indicates that the current node will be overwritten

        """
        overwrite = overwrite if overwrite is not None else self.overwrite
        if self.node_exists(node):
            if not overwrite:
                raise PathNodeMapError(f"A path and node at '{node}' already exists in the Map")
            else:
                logger.debug(f"The node at '{node}' will be overwritten")

    def _validate_node(self, node: PathNode, overwrite: Optional[bool] = None):
        """Validate constraints on the node to be inserted into the PathNodeMap.

        Args:
            node (PathNode): The PathNode instance to validate.

        Raises:
            PathNodeMapError: If any constraint is violated.

        """

        try:

            PathNode.is_valid_node(node)
            self._validate_new_node_path(node, overwrite=overwrite)

            logger.debug(f"Validated node: {node}")

        except Exception as e:
            raise PathNodeMapError(f"Error validating constraints on node insertion: {e}") from e

    @classmethod
    def _keep_terminal_paths(
        cls,
        path_list: Union[
            list[ProcessingPath],
            Set[ProcessingPath],
            Generator[ProcessingPath, None, None],
        ],
    ) -> Set[ProcessingPath]:
        """Filter a list of paths to keep only terminal paths.

        Args:
            path_list (list[ProcessingPath]): The list of paths to filter.
            Returns:
                Set[ProcessingPath]: A set of terminal paths.

        """
        sorted_path_list = sorted(
            path_list,
            key=lambda path: path._to_alphanum(depth_first=True),
            reverse=True,
        )
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
    def format_terminal_nodes(
        cls, node_obj: Union[MutableMapping, PathNodeMap, PathNode]
    ) -> dict[ProcessingPath, PathNode]:
        """
        Recursively iterate over terminal nodes from Path Node Maps and retrieve only terminal_nodes
        Args:
            node_obj (Union[dict,PathNodeMap]): PathNode map or node dictionary containing either nested or already flattened terminal_paths
        Returns:
            item (dict): the flattened terminal paths extracted from the inputted node_obj
        """

        if isinstance(node_obj, PathNodeMap):
            return node_obj.data

        if isinstance(node_obj, dict):
            return {node.path: node for node in node_obj.values() if PathNode.is_valid_node(node)}

        if isinstance(node_obj, PathNode):
            return {node_obj.path: node_obj}

        raise ValueError(
            f"Invalid input to node_obj: argument must be a Path Node Map or a PathNode. Received ({type(node_obj)})"
        )

    @staticmethod
    def _transform_key(key: Union[str, ProcessingPath], delimiter: str) -> ProcessingPath:
        """For coercing string type keys into ProcessingPaths if not already path types
        Args:
            path (Union[str, list[str]]): The initial path, either as a string or a list of strings.
            delimiter (str): The delimiter used to separate components in the path.
        Returns:
            ProcessingPath: the path leading to the node that this object corresponds to
        """
        if not isinstance(key, ProcessingPath):
            transformed_key = ProcessingPath.to_processing_path(key, component_types=None, delimiter=delimiter)
            if key is not transformed_key:
                logger.debug(f"converted {key} --> {transformed_key}")
            return transformed_key
        return key

    def _validate_input(
        self,
        path: Union[str, ProcessingPath],
        node: PathNode,
        overwrite: Optional[bool] = None,
    ) -> ProcessingPath:
        """Method of performing key-value pair validation while returning the path if the pair is valid:

        Args:
            path (Union[str, ProcessingPath]): The initial path, formatted as a string or a ProcessingPath instance.
            node (PathNode): The PathNode instance to validate.
        Returns:
            ProcessingPath: A ProcessingPath instance.

        Raises:
            PathNodeMapError If the path object, node path is invalid, or combination of the key and node pair is invalid.

        """
        try:
            self._validate_node(node, overwrite)
            transformed_path = self._transform_key(path, delimiter=node.path.delimiter)
            self._validate_key_value_pair(transformed_path, node)
            return transformed_path
        except Exception as e:
            raise PathNodeMapError(f"Error validating path ({path}) and node ({node}): {e}") from e

    @classmethod
    def format_mapping(
        cls,
        key_value_pairs: Union[PathNodeMap, MutableMapping[ProcessingPath, PathNode], dict[str, PathNode]],
    ) -> dict[ProcessingPath, PathNode]:
        """Takes a dictionary or a PathNodeMap Transforms the string keys in a dictionary into Processing paths and
        returns the mapping.

        Args:
            key_value_pairs (Union[dict[ProcessingPath, PathNode], dict[str, PathNode]]): The dictionary of key-value pairs to transform.
        Returns:
            dict[ProcessingPath, PathNode]: a dictionary of validated path, node pairings
        Raises:
            PathNodeMapError: If the validation process fails.

        """
        try:
            terminal_nodes = cls.format_terminal_nodes(key_value_pairs)
            if len(terminal_nodes) == 0:
                return terminal_nodes
            terminal_paths = cls._keep_terminal_paths({node.path for node in terminal_nodes.values()})
            filtered_dict = {path: node for path, node in terminal_nodes.items() if path in terminal_paths}
        except Exception as e:
            raise PathNodeMapError(f":The validation process for the input pairs failed: {e}")

        return filtered_dict

    #   def _extract_node(self, *nodes) -> Optional[PathNode]:
    #       """
    #       Attempts to extract a node from arguments of arbitrary lengths.
    #       If there is more than one node, this method will return None with
    #       the aim of deferring processing multiple nodes to other helper methods

    #       """
    #       if isinstance(nodes, PathNode):
    #           return nodes

    #       if isinstance(nodes, (list, tuple)) and len(nodes) == 1:
    #           node = nodes[0]
    #           return node if isinstance(node, PathNode) else None
    #       return None

    @classmethod
    def _format_nodes_as_dict(cls, *nodes, **path_nodes) -> Union[
        PathNodeMap,
        dict[ProcessingPath, PathNode],
    ]:
        """Helper function to format the input arguments as a dictionary."""

        type_verified = False
        node_dict = cls.format_mapping(path_nodes) if path_nodes else {}

        if not nodes:
            return node_dict

        formatted_nodes: tuple | MutableMapping | list | set | Generator = (
            nodes[0] if (isinstance(nodes, tuple) and len(nodes) == 1 and not isinstance(nodes[0], PathNode)) else nodes
        )

        if isinstance(formatted_nodes, PathNode):
            processed_nodes: Optional[MutableMapping] = {formatted_nodes.path: formatted_nodes}
            type_verified = True
        elif isinstance(formatted_nodes, (set, Sequence, GeneratorType)):
            processed_nodes = {node.path: node for node in formatted_nodes if PathNode.is_valid_node(node)}
            type_verified = True
        elif isinstance(formatted_nodes, MutableMapping):
            processed_nodes = formatted_nodes
        else:
            processed_nodes = None

        if isinstance(processed_nodes, (MutableMapping, PathNodeMap)) and (
            type_verified
            or isinstance(processed_nodes, PathNodeMap)
            or all(isinstance(node, PathNode) for node in processed_nodes.values())
        ):

            node_dict = node_dict | cls.format_mapping(processed_nodes)

            return node_dict

        raise PathNodeMapError(
            "Could not format the input as a dictionary of nodes: Expected the input to be a "
            f"PathNode or sequence/mapping containing PathNodes. Instead received {type(unlist_1d(nodes))}"
        )

    def update(  # type: ignore[override]
        self,
        *args,
        overwrite: Optional[bool] = None,
        **kwargs: Mapping[str | ProcessingPath, PathNode],
    ) -> None:
        """Updates the PathNodeMap instance with new key-value pairs.

        Args:
            *args (Union[PathNodeMap,dict[ProcessingPath, PathNode],dict[str, PathNode]]): PathNodeMap or dictionary containing the key-value pairs to append to the PathNodeMap
            overwrite (bool): Flag indicating whether to overwrite existing values if the key already exists.
            *kwargs (PathNode): Path Nodes using the path as the argument name to append to the PathNodeMap
        Returns

        """
        logger.debug("Updating PathNodeMap instance")  # Log updating

        node_dict = self._format_nodes_as_dict(*args, **kwargs)

        self._update(node_dict, overwrite)
        logger.debug("Updated successfully")

    def _update(
        self,
        node_dict: Union[
            PathNodeMap,
            dict[ProcessingPath, PathNode],
            dict[ProcessingPath, PathNode],
        ],
        overwrite: Optional[bool] = None,
    ) -> None:
        """Helper method for directly updating the current path node map skipping previously performed validation
        steps."""
        default_overwrite = overwrite if overwrite is not None else self.overwrite
        try:
            # setting and using self.overwrite as a temporary overwrite parameter
            self.overwrite = default_overwrite
            super().update(node_dict)
        except Exception as e:
            raise PathNodeMapError(f"An error occurred during updating: {e}") from e
        finally:
            self.overwrite = default_overwrite

    def get(  # type: ignore[override]
        self, key: Union[str, ProcessingPath], default: Optional[PathNode] = None
    ) -> Optional[PathNode]:
        """Gets an item from the PathNodeMap instance. If the value isn't available, this method will return the value
        specified in default.

        Args:
            key (Union[str,ProcessingPath]): The key (Processing path) If string, coerces to a ProcessingPath.

        Returns:
            PathNode: The value (PathNode instance).

        """
        if key is None:
            return None

        if isinstance(key, PathNode):
            key = key.path

        key = self._validate_path(key)
        return super().get(key)

    @property
    def record_indices(self) -> list[int]:
        """
        Helper property for retrieving the full list of all record indices across all paths for the current map
        Note: This assumes that all paths within the current map are derived from a list of records where every
        path's first element denotes its initial position in a list with nested json components

        Returns:
            list[int]: A list containing integers denoting individual records found in each path
        """
        return sorted({path.record_index for path in self.nodes})

    def get_node(self, key: Union[str, ProcessingPath], default: Optional[PathNode] = None) -> Optional[PathNode]:
        """Helper method for retrieving a path node in a standardized way."""
        return self.get(key, default)

    def __getitem__(self, key: Union[str, ProcessingPath]) -> PathNode:
        """Gets an item from the PathNodeMap instance.

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
                            this method coerces string inputs into a ProcessingPath

        Raises:
            InvalidProcessingPathError if the value is anything other than a string/path object already
        """
        if isinstance(key, str):
            key = ProcessingPath.with_inferred_delimiter(key)
        if not isinstance(key, ProcessingPath):
            raise InvalidProcessingPathError(
                f"Unexpected value type observed: {type(key)}): Expected a ProcessingPath/string"
            )
        return key

    def add(self, node: PathNode, overwrite: Optional[bool] = None, inplace: bool = True) -> Optional[PathNodeMap]:
        """Add a node to the PathNodeMap instance.

        Args:
            node (PathNode): The node to add.
            overwrite (bool): Flag indicating whether to overwrite existing values if the key already exists.

        Raises:
            PathNodeMapError: If any error occurs while adding the node.

        """

        default_overwrite = self.overwrite
        try:
            if not inplace:
                path_node_map = copy.deepcopy(self)
                path_node_map.add(node, overwrite=overwrite, inplace=True)
                return path_node_map
            if PathNode.is_valid_node(node):
                logger.debug(f"Adding node: '{node}'")
            self.__setitem__(
                node.path,
                node,
                # overwrite=overwrite
            )
        except Exception as e:
            raise PathNodeMapError(f"Error adding nodes to PathNodeMap: {e}") from e
        finally:
            self.overwrite = default_overwrite
        return None

    def remove(self, node: Union[ProcessingPath, PathNode, str], inplace: bool = True) -> Optional[PathNodeMap]:
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
                path_node_map = copy.deepcopy(self)
                path_node_map.remove(node, inplace=False)
                return path_node_map

            if not isinstance(node, (str, ProcessingPath, PathNode)):
                raise PathNodeMapError(f"Invalid type for node: {type(node)}. Must be a ProcessingPath or a PathNode.")

            path = node.path if isinstance(node, PathNode) else ProcessingPath.to_processing_path(node)

            logger.debug(f"Removing node: '{node}'")
            del self.data[path]

        except Exception as e:
            raise PathNodeMapError(f"Error removing paths from PathNodeMap: {e}") from e
        return None

    def __copy__(self) -> PathNodeMap:
        """Create a copy of the current path-node combinations and their contents.

        Returns:
            SparsePathNodeMap: A new map of path-node combinations  with the same attributes
            and values as the current map.

        """
        try:
            path_node_map = self.__class__.__new__(self.__class__)
            path_node_map.__dict__ = self.__dict__.copy()
            return path_node_map

        except Exception as e:

            logger.exception(f'Error copying map "{self}": {e}')
            raise PathNodeMapError(f"Error copying map: {e}")


__all__ = ["PathNodeMap"]
