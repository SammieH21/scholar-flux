from __future__ import annotations

from typing import Optional, Union, Generator, Sequence, Mapping
from collections import UserDict
from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    InvalidPathNodeError,
    PathNodeMapError,
    PathRecordMapError,
    PathChainMapError,
)

from scholar_flux.utils.paths import ProcessingPath, PathNode, PathNodeMap

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class PathRecordMap(PathNodeMap):
    """
    A dictionary-like class that maps Processing paths to PathNode objects.
    """

    def __init__(
        self,
        *nodes: Union[
            PathNode,
            Generator[PathNode, None, None],
            set[PathNode],
            Sequence[PathNode],
            Mapping[str | ProcessingPath, PathNode],
        ],
        record_index: Optional[int | str] = None,
        cache: Optional[bool] = None,
        allow_terminal: Optional[bool] = False,
        overwrite: Optional[bool] = True,
        **path_nodes: Mapping[str | ProcessingPath, PathNode],
    ) -> None:
        prepared_nodes = self._format_nodes_as_dict(*nodes, **path_nodes)
        if not record_index and prepared_nodes:
            record_index, _ = self._prepare_inputs(list(prepared_nodes.values()))

        if record_index is None or not isinstance(record_index, int):
            raise PathRecordMapError("A numeric record index is missing and could not be inferred from the input nodes")

        self.record_index: int = int(record_index)
        super().__init__(cache=cache, allow_terminal=allow_terminal, overwrite=overwrite)
        self.update(prepared_nodes)

    @classmethod
    def _extract_record_index(cls, path: Union[str, int, ProcessingPath] | PathNode) -> int:
        try:
            if isinstance(path, int):
                return path
            if isinstance(path, str) and path.isnumeric():
                return int(path)

            if isinstance(path, PathNode):
                path = path.path

            inferred_path = path if isinstance(path, ProcessingPath) else ProcessingPath.with_inferred_delimiter(path)
            path_key = int(inferred_path.components[0])
            return path_key
        except (TypeError, AttributeError, InvalidProcessingPathError, ValueError) as e:
            raise InvalidProcessingPathError(
                f"Could not extract a record path for value of class {type(path)}, "
                f"Expected a ProcessingPath with a numeric value in the first component"
            ) from e

    @classmethod
    def _prepare_inputs(
        cls, mapping: PathNode | dict[str | ProcessingPath, PathNode] | PathNodeMap | Sequence[PathNode] | set[PathNode]
    ) -> tuple[int, set[PathNode] | Sequence[PathNode]]:

        try:
            if isinstance(mapping, (dict, PathNodeMap)):
                nodes: Sequence[PathNode] | set[PathNode] = list(mapping.values())

            elif isinstance(mapping, PathNode):
                nodes = [mapping]
            else:
                nodes = mapping

            if not (isinstance(nodes, (Sequence, set)) and all(PathNode.is_valid_node(node) for node in nodes)):
                raise PathRecordMapError("Expected a sequence of nodes, but at least one value is of a different type")

            record_indices = list({node.record_index for node in nodes})

            if len(record_indices) != 1:
                raise PathRecordMapError(
                    "Expected a mapping or sequence with exactly 1 record_index, " f"Received: {record_indices}"
                )
            return record_indices[0], nodes
        except (PathNodeMapError, InvalidPathNodeError, InvalidProcessingPathError) as e:
            raise PathRecordMapError(f"Encountered an error on the preparation of inputs for a PathRecordMap: {e}")

    @classmethod
    def from_mapping(
        cls,
        mapping: (
            dict[str | ProcessingPath, PathNode] | PathNodeMap | Sequence[PathNode] | set[PathNode] | PathRecordMap
        ),
        cache: Optional[bool] = None,
    ) -> PathRecordMap:
        """Helper method for coercing types into a PathRecordMap"""

        if isinstance(mapping, PathRecordMap):
            return mapping

        record_index, nodes = cls._prepare_inputs(mapping)
        return cls(*nodes, record_index=record_index, cache=cache)

    def _validate_node(self, node: PathNode, overwrite: Optional[bool] = None):
        """
        Validate constraints on the node to be inserted into the PathNodeMap.

        Args:
            node (PathNode): The PathNode instance to validate.

        Raises:
            PathNodeMapError: If any constraint is violated.
        """

        try:

            PathNode.is_valid_node(node)
            if self._extract_record_index(node) != self.record_index:
                raise PathRecordMapError(
                    "Expected the first element in the path of the node to be the same type as the "
                    f"record index of the current PathRecordMap. Received: {node.path}"
                )

            self._validate_new_node_path(node, overwrite=overwrite)

            logger.debug(f"Validated node: {node}")

        except Exception as e:
            raise PathRecordMapError(f"Error validating constraints on node insertion: {e}") from e


class PathChainMap(UserDict[int, PathRecordMap]):
    """
    A dictionary-like class that maps Processing paths to PathNode objects.
    """

    DEFAULT_USE_CACHE = PathRecordMap.DEFAULT_USE_CACHE

    def __init__(
        self,
        *record_maps: Union[
            PathRecordMap,
            PathNodeMap,
            PathNode,
            Generator[PathNode, None, None],
            Sequence[PathNode],
            Mapping[int | str | ProcessingPath, PathNode],
            Mapping[int, PathNodeMap],
        ],
        cache: Optional[bool] = None,
        **path_record_maps: Union[
            PathRecordMap,
            PathNodeMap,
            PathNode,
            Generator[PathNode, None, None],
            Sequence[PathNode],
            Mapping[int | str | ProcessingPath, PathNode],
            Mapping[int, PathNodeMap],
        ],
    ) -> None:
        """
        Initializes the PathRecordMap instance.
        """
        self.cache = cache if cache is not None else PathRecordMap.DEFAULT_USE_CACHE
        self.data: dict[int, PathRecordMap] = self._resolve_record_maps(
            *record_maps, *path_record_maps.values(), use_cache=self.cache
        )

    def __getitem__(self, key: Union[int, ProcessingPath]) -> PathRecordMap:
        """
        Retrieve a path record map from the PathChainMap if the key exists.

        Args:
            key (Union[int, ProcessingPath]): The key (Processing path) If string, coerces to a ProcessingPath.
        Returns:
            PathNode: The value (PathNode instance).
        """
        record_index = self._extract_record_index(key)

        return self.data[record_index]

    def __contains__(self, key: object) -> bool:
        """
        Checks whether the key prefix exists in the PathChainMap instance.

        If a full processing path is passed, check for whether the path exists within the mapping
        under the same prefix

        Args:
            key (Union[str, ProcessingPath]): The key (Processing path) prefix to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """

        if key is None:
            return False

        # type validation occurs here
        if isinstance(key, PathNode):
            path = key.path
        else:
            path = ProcessingPath.with_inferred_delimiter(str(key)) if not isinstance(key, ProcessingPath) else key

        path_key = self._extract_record_index(path)

        mapping = self.data.get(path_key)

        if mapping is None:
            return False

        # if we're checking with single path prefix, return True
        if len(path) == 1:
            return bool(mapping)

        # if we have a full path, check whether the mapping contains the path
        return path in mapping

    def retrieve(self, key: Union[str, ProcessingPath], default: Optional[PathNode] = None) -> Optional[PathNode]:
        """Helper method for retrieving a path node in a standardized way across PathNodeMaps"""
        mapping = self.get(key)
        return mapping.get(key, default) if mapping is not None else None

    @property
    def nodes(self) -> list[PathNode]:
        """enables looping over paths stored across maps"""
        return [node for mapping in self.data.values() for node in mapping.values()]

    @property
    def paths(self) -> list[ProcessingPath]:
        """enables looping over nodes stored across maps"""
        return [path for mapping in self.data.values() for path in mapping]

    @classmethod
    def _extract_record_index(cls, path: Union[str, int, ProcessingPath]) -> int:
        """Helper method for extracting the path record index for a path"""
        return PathRecordMap._extract_record_index(path)

    @property
    def record_indices(self) -> list[int]:
        """
        Helper property for retrieving the full list of all record indices across all paths for the current map
        Note: A core requirement of the ChainMap is that each PathRecordMap indicates the position of a record
        in a nested JSON structure. This property is a helper method to quickly retrieve the full list of sorted
        record_indices.

        Returns:
            list[int]: A list containing integers denoting individual records found in each path
        """
        return sorted(record_map.record_index for record_map in self.data.values())

    def filter(
        self,
        prefix: ProcessingPath | str | int,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> dict[ProcessingPath, PathNode]:
        """
        Filter the PathChainMap for paths with the given prefix.
        Args:
            prefix (ProcessingPath): The prefix to search for.
            min_depth (Optional[int]): The minimum depth to search for. Default is None.
            max_depth (Optional[int]): The maximum depth to search for. Default is None.
            from_cache (Optional[bool]): Whether to use cache when filtering based on a path prefix.
        Returns:
            dict[Optional[ProcessingPath], Optional[PathNode]]: A dictionary of paths with the given prefix and their corresponding
            terminal_nodes
        Raises:
            PathRecordMapError: If an error occurs while filtering the PathNodeMap.
        """
        try:
            record_index = self._extract_record_index(prefix)

            mapping = self.data.get(record_index)

            if mapping:
                return mapping.filter(prefix=prefix, min_depth=min_depth, max_depth=max_depth)

            return {}

        except Exception as e:
            raise PathNodeMapError(f"Encountered an error filtering PathNodeMaps within the ChainMap: {e}")

    def node_exists(self, node: Union["PathNode", ProcessingPath]) -> bool:
        """Helper method to validate whether the current node exists"""
        if not isinstance(node, (PathNode, ProcessingPath)):
            raise InvalidPathNodeError(f"Key must be node or path. Received '{type(node)}'")

        if isinstance(node, PathNode):
            node = node.path

        record_index = self._extract_record_index(node)

        mapping = self.data.get(record_index)
        return mapping is not None and mapping.get(node) is not None

    @classmethod
    def _resolve_record_maps(cls, *args, use_cache: Optional[bool] = None) -> dict[int, PathRecordMap]:
        """Helper method for resolving groups of nodes and record maps into an integrated structure"""

        mapped_groups: dict[int, PathRecordMap] = {}

        if len(args) == 0:
            return mapped_groups

        if len(args) == 1:
            data = args[0]

            if (isinstance(data, (set, Sequence, Mapping)) and not data) or data is None:
                return mapped_groups

        if isinstance(args, PathNodeMap) and not isinstance(args, PathRecordMap):
            args = list(args.values())
            logger.warning(f"Encountered a path node map, parsed args {args}")

        for value in args:

            if isinstance(value, (PathNodeMap, dict, Sequence, set)):
                value = PathRecordMap.from_mapping(value, cache=use_cache)

            if isinstance(value, PathRecordMap):
                record_index = value.record_index

                if record_index not in mapped_groups:
                    mapped_groups[record_index] = PathRecordMap(record_index=record_index, cache=use_cache)
                mapped_groups[record_index] |= value

            elif isinstance(value, PathNode):
                record_index = cls._extract_record_index(value.path)
                (
                    mapped_groups.setdefault(
                        record_index, PathRecordMap(record_index=record_index, cache=use_cache)
                    ).add(value)
                )

            else:
                raise PathChainMapError(
                    "Expected either a PathRecordMap or a list of nodes to resolve into "
                    f"a record map, Received element of type {type(value)}"
                )
        return mapped_groups

    def update(  # type: ignore
        self,
        *args,
        overwrite: Optional[bool] = None,
        **kwargs: dict[str, PathNode] | dict[Union[str, ProcessingPath], PathRecordMap],
    ) -> None:
        """
        Updates the PathNodeMap instance with new key-value pairs.

        Args:
            *args (Union["PathNodeMap",dict[ProcessingPath, PathNode],dict[str, PathNode]]): PathNodeMap or dictionary containing the key-value pairs to append to the PathNodeMap
            overwrite (bool): Flag indicating whether to overwrite existing values if the key already exists.
            *kwargs (PathNode): Path Nodes using the path as the argument name to append to the PathNodeMap
        Returns
        """

        record_map_dict = self._resolve_record_maps(*args, *kwargs.values())

        for record_map in record_map_dict.values():
            record_index = record_map.record_index

            (
                self.data.setdefault(record_index, PathRecordMap(record_index=record_index)).update(
                    dict(record_map), overwrite=overwrite
                )
            )

        logger.debug("Updated successfully")

    def get(  # type: ignore[override]
        self, key: Union[str, ProcessingPath], default: Optional[PathRecordMap] = None
    ) -> Optional[PathRecordMap]:
        """
        Gets an item from the PathRecordMap instance. If the value isn't available,
        this method will return the value specified in default

        Args:
            key (Union[str,ProcessingPath]): The key (Processing path) If string, coerces to a ProcessingPath.

        Returns:
            PathRecordMap: A record map instance
        """

        key = PathNodeMap._validate_path(key)
        record_index = self._extract_record_index(key)

        return self.data.get(record_index, default)

    def add(self, node: PathNode | PathRecordMap, overwrite: Optional[bool] = None):
        """
        Add a node to the PathNodeMap instance.

        Args:
            node (PathNode): The node to add.
            overwrite (bool): Flag indicating whether to overwrite existing values if the key already exists.

        Raises:
            PathNodeMapError: If any error occurs while adding the node.
        """

        try:
            self.update(node, overwrite=overwrite)
        except Exception as e:
            raise PathNodeMapError(f"Error adding nodes to PathChainMap: {e}") from e

    def remove(self, node: Union[ProcessingPath, "PathNode", str]):
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
            path = node.path if isinstance(node, PathNode) else ProcessingPath.to_processing_path(node)
            mapping: PathRecordMap | dict[ProcessingPath, PathNode] = self.get(path) or {}
            if removed_node := mapping.pop(path, None):
                logger.debug(f"Removing node: '{removed_node}'")

        except Exception as e:
            raise PathNodeMapError(f"Error removing paths from PathNodeMap: {e}") from e
