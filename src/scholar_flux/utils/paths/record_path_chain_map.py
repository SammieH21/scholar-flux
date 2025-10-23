# /utils/paths/record_path_chain_map.py
"""The scholar_flux.utils.paths.path_node_map module builds on top of the original PathNodeMap to further specialize the
map implementation toward the nested dictionary records that can be found within paginated data.

This module implements the RecordPathNodeMap and RecordPathChainMap, respectively to process batches of nodes at a time
that all apply to a single record while allowing speedups to cache when retaining only terminal nodes via set/dictionary
operations.

"""
from __future__ import annotations

from typing import Optional, Union, Generator, Sequence, Mapping
from collections import UserDict
from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    InvalidPathNodeError,
    PathNodeMapError,
    RecordPathNodeMapError,
    RecordPathChainMapError,
)

from scholar_flux.utils.paths import ProcessingPath, PathNode, PathNodeMap

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class RecordPathNodeMap(PathNodeMap):
    """A dictionary-like class that maps Processing paths to PathNode objects using record indexes.

    This implementation inherits from the PathNodeMap class and constrains the allowed nodes to those that begin with a
    numeric record index. Where each index indicates a record and nodes represent values associated with the record.

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
        use_cache: Optional[bool] = None,
        allow_terminal: Optional[bool] = False,
        overwrite: Optional[bool] = True,
        **path_nodes: Mapping[str | ProcessingPath, PathNode],
    ) -> None:
        """Initializes the RecordPathNodeMap using a similar set of inputs as the original PathNodeMap.

        This implementation constraints the inputted nodes to a singular numeric key index that all nodes must begin
        with. If nodes are provided without the key, then the `record_index` is inferred for the inputs.

        """
        prepared_nodes = self._format_nodes_as_dict(*nodes, **path_nodes)
        if not record_index and prepared_nodes:
            record_index, _ = self._prepare_inputs(list(prepared_nodes.values()))

        if record_index is None or not isinstance(record_index, int):
            raise RecordPathNodeMapError(
                "A numeric record index is missing and could not be inferred from the input nodes"
            )

        self.record_index: int = int(record_index)
        super().__init__(use_cache=use_cache, allow_terminal=allow_terminal, overwrite=overwrite)
        self.update(prepared_nodes)

    @classmethod
    def _extract_record_index(cls, path: Union[str, int, ProcessingPath] | PathNode) -> int:
        """Helper method that retrieves a numeric record index that corresponds to the inputted node, path, or
        string."""
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
        """Helper method that processes a mapping or sequence of nodes to prepare the record index and nodes used to
        create a RecordPathNodeMap structure.

        Args:
            mapping (PathNode | dict[str | ProcessingPath, PathNode] | PathNodeMap | Sequence[PathNode] | set[PathNode]):
                A path node, sequence of path nodes, or dictionary-like mapping of path-node combinations. This
                input is parsed and prepared to use as direct input to create a new RecordPathNodeMap.

        Returns:
            tuple[int, set[PathNode] | Sequence[PathNode]]: A record path index associated with the path-node mappings
                                                            and the sequence of nodes extracted from the input

        """

        try:
            if isinstance(mapping, (dict, PathNodeMap)):
                nodes: Sequence[PathNode] | set[PathNode] = list(mapping.values())

            elif isinstance(mapping, PathNode):
                nodes = [mapping]
            else:
                nodes = mapping

            if not (isinstance(nodes, (Sequence, set)) and all(PathNode.is_valid_node(node) for node in nodes)):
                raise RecordPathNodeMapError(
                    "Expected a sequence of nodes, but at least one value is of a different type"
                )

            record_indices = list({node.record_index for node in nodes})

            if len(record_indices) != 1:
                raise RecordPathNodeMapError(
                    "Expected a mapping or sequence with exactly 1 record_index, " f"Received: {record_indices}"
                )
            return record_indices[0], nodes
        except (PathNodeMapError, InvalidPathNodeError, InvalidProcessingPathError) as e:
            raise RecordPathNodeMapError(
                f"Encountered an error on the preparation of inputs for a RecordPathNodeMap: {e}"
            )

    @classmethod
    def from_mapping(
        cls,
        mapping: (
            dict[str | ProcessingPath, PathNode] | PathNodeMap | Sequence[PathNode] | set[PathNode] | RecordPathNodeMap
        ),
        use_cache: Optional[bool] = None,
    ) -> RecordPathNodeMap:
        """Helper method for coercing types into a RecordPathNodeMap."""

        if isinstance(mapping, RecordPathNodeMap):
            return mapping

        record_index, nodes = cls._prepare_inputs(mapping)
        return cls(*nodes, record_index=record_index, use_cache=use_cache)

    def _validate_node(self, node: PathNode, overwrite: Optional[bool] = None):
        """Validate constraints on the node to be inserted into the PathNodeMap.

        Args:
            node (PathNode): The PathNode instance to validate.

        Raises:
            PathNodeMapError: If any constraint is violated.

        """

        try:

            PathNode.is_valid_node(node)
            if self._extract_record_index(node) != self.record_index:
                raise RecordPathNodeMapError(
                    "Expected the first element in the path of the node to be the same type as the "
                    f"record index of the current RecordPathNodeMap. Received: {node.path}"
                )

            self._validate_new_node_path(node, overwrite=overwrite)

            logger.debug(f"Validated node: {node}")

        except Exception as e:
            raise RecordPathNodeMapError(f"Error validating constraints on node insertion: {e}") from e


class RecordPathChainMap(UserDict[int, RecordPathNodeMap]):
    """A dictionary-like class that maps Processing paths to PathNode objects."""

    DEFAULT_USE_CACHE = RecordPathNodeMap.DEFAULT_USE_CACHE

    def __init__(
        self,
        *record_maps: Union[
            RecordPathNodeMap,
            PathNodeMap,
            PathNode,
            Generator[PathNode, None, None],
            Sequence[PathNode],
            Mapping[int | str | ProcessingPath, PathNode],
            Mapping[int, PathNodeMap],
        ],
        use_cache: Optional[bool] = None,
        **path_record_maps: Union[
            RecordPathNodeMap,
            PathNodeMap,
            PathNode,
            Generator[PathNode, None, None],
            Sequence[PathNode],
            Mapping[int | str | ProcessingPath, PathNode],
            Mapping[int, PathNodeMap],
        ],
    ) -> None:
        """Initializes the RecordPathNodeMap instance."""
        self.use_cache = use_cache if use_cache is not None else RecordPathNodeMap.DEFAULT_USE_CACHE
        self.data: dict[int, RecordPathNodeMap] = self._resolve_record_maps(
            *record_maps, *path_record_maps.values(), use_cache=self.use_cache
        )

    def __getitem__(self, key: Union[int, ProcessingPath]) -> RecordPathNodeMap:
        """Retrieve a path record map from the RecordPathChainMap if the key exists.

        Args:
            key (Union[int, ProcessingPath]): The key (Processing path) If string, coerces to a ProcessingPath.
        Returns:
            PathNode: The value (PathNode instance).

        """
        record_index = self._extract_record_index(key)

        return self.data[record_index]

    def __contains__(self, key: object) -> bool:
        """Checks whether the key prefix exists in the RecordPathChainMap instance.

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

    def get_node(self, key: Union[str, ProcessingPath], default: Optional[PathNode] = None) -> Optional[PathNode]:
        """Helper method for retrieving a path node in a standardized way across PathNodeMaps."""
        mapping = self.get(key)
        return mapping.get(key, default) if mapping is not None else None

    @property
    def nodes(self) -> list[PathNode]:
        """Enables looping over paths stored across maps."""
        return [node for mapping in self.data.values() for node in mapping.values()]

    @property
    def paths(self) -> list[ProcessingPath]:
        """Enables looping over nodes stored across maps."""
        return [path for mapping in self.data.values() for path in mapping]

    @classmethod
    def _extract_record_index(cls, path: Union[str, int, ProcessingPath]) -> int:
        """Helper method for extracting the path record index for a path."""
        return RecordPathNodeMap._extract_record_index(path)

    @property
    def record_indices(self) -> list[int]:
        """
        Helper property for retrieving the full list of all record indices across all paths for the current map
        Note: A core requirement of the ChainMap is that each RecordPathNodeMap indicates the position of a record
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
        from_cache: Optional[bool] = None,
    ) -> dict[ProcessingPath, PathNode]:
        """Filter the RecordPathChainMap for paths with the given prefix.

        Args:
            prefix (ProcessingPath): The prefix to search for.
            min_depth (Optional[int]): The minimum depth to search for. Default is None.
            max_depth (Optional[int]): The maximum depth to search for. Default is None.
            from_cache (Optional[bool]): Whether to use cache when filtering based on a path prefix.
        Returns:
            dict[Optional[ProcessingPath], Optional[PathNode]]: A dictionary of paths with the given prefix and their corresponding
            terminal_nodes
        Raises:
            RecordPathNodeMapError: If an error occurs while filtering the PathNodeMap.

        """
        try:
            record_index = self._extract_record_index(prefix)

            mapping = self.data.get(record_index)

            if mapping:
                return mapping.filter(prefix=prefix, min_depth=min_depth, max_depth=max_depth, from_cache=from_cache)

            return {}

        except Exception as e:
            raise PathNodeMapError(f"Encountered an error filtering PathNodeMaps within the ChainMap: {e}")

    def node_exists(self, node: Union["PathNode", ProcessingPath]) -> bool:
        """Helper method to validate whether the current node exists."""
        if not isinstance(node, (PathNode, ProcessingPath)):
            raise InvalidPathNodeError(f"Key must be node or path. Received '{type(node)}'")

        if isinstance(node, PathNode):
            node = node.path

        record_index = self._extract_record_index(node)

        mapping = self.data.get(record_index)
        return mapping is not None and mapping.get(node) is not None

    @classmethod
    def _resolve_record_maps(cls, *args, use_cache: Optional[bool] = None) -> dict[int, RecordPathNodeMap]:
        """Helper method for resolving groups of nodes and record maps into an integrated structure."""

        mapped_groups: dict[int, RecordPathNodeMap] = {}

        if len(args) == 0:
            return mapped_groups

        if len(args) == 1:
            data = args[0]

            if (isinstance(data, (set, Sequence, Mapping)) and not data) or data is None:
                return mapped_groups

        if isinstance(args, PathNodeMap) and not isinstance(args, RecordPathNodeMap):
            args = list(args.values())
            logger.warning(f"Encountered a path node map, parsed args {args}")

        for value in args:

            if isinstance(value, (PathNodeMap, dict, Sequence, set)):
                value = RecordPathNodeMap.from_mapping(value, use_cache=use_cache)

            if isinstance(value, RecordPathNodeMap):
                record_index = value.record_index

                if record_index not in mapped_groups:
                    mapped_groups[record_index] = RecordPathNodeMap(record_index=record_index, use_cache=use_cache)
                mapped_groups[record_index] |= value

            elif isinstance(value, PathNode):
                record_index = cls._extract_record_index(value.path)
                (
                    mapped_groups.setdefault(
                        record_index, RecordPathNodeMap(record_index=record_index, use_cache=use_cache)
                    ).add(value)
                )

            else:
                raise RecordPathChainMapError(
                    "Expected either a RecordPathNodeMap or a list of nodes to resolve into "
                    f"a record map, Received element of type {type(value)}"
                )
        return mapped_groups

    def update(
        self,
        *args,
        overwrite: Optional[bool] = None,
        **kwargs: dict[str, PathNode] | dict[Union[str, ProcessingPath], RecordPathNodeMap],
    ) -> None:
        """Updates the PathNodeMap instance with new key-value pairs.

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
                self.data.setdefault(record_index, RecordPathNodeMap(record_index=record_index)).update(
                    dict(record_map), overwrite=overwrite
                )
            )

        logger.debug("Updated successfully")

    def get(  # type: ignore[override]
        self, key: Union[str, ProcessingPath], default: Optional[RecordPathNodeMap] = None
    ) -> Optional[RecordPathNodeMap]:
        """Gets an item from the RecordPathNodeMap instance. If the value isn't available, this method will return the
        value specified in default.

        Args:
            key (Union[str,ProcessingPath]): The key (Processing path) If string, coerces to a ProcessingPath.

        Returns:
            RecordPathNodeMap: A record map instance

        """

        key = PathNodeMap._validate_path(key)
        record_index = self._extract_record_index(key)

        return self.data.get(record_index, default)

    def add(self, node: PathNode | RecordPathNodeMap, overwrite: Optional[bool] = None):
        """Add a node to the PathNodeMap instance.

        Args:
            node (PathNode): The node to add.
            overwrite (bool): Flag indicating whether to overwrite existing values if the key already exists.

        Raises:
            PathNodeMapError: If any error occurs while adding the node.

        """

        try:
            self.update(node, overwrite=overwrite)
        except Exception as e:
            raise PathNodeMapError(f"Error adding nodes to RecordPathChainMap: {e}") from e

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
            mapping: RecordPathNodeMap | dict[ProcessingPath, PathNode] = self.get(path) or {}
            if removed_node := mapping.pop(path, None):
                logger.debug(f"Removing node: '{removed_node}'")

        except Exception as e:
            raise PathNodeMapError(f"Error removing paths from PathNodeMap: {e}") from e


__all__ = ["RecordPathNodeMap", "RecordPathChainMap"]
