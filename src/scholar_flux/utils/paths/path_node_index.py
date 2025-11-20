# /utils/paths/path_node_index.py
"""The scholar_flux.utils.paths.path_node_index module implements the PathNodeIndex class that uses trie-based logic to
facilitate the processing of JSON data structures.

The PathNodeIndex is responsible for orchestrating JSON data discovery, processing, and flattening to abstract JSON data
into path-node pairs indicate the location of terminal values and the path location of the terminal-values within a
nested JSON data structure.

"""
from __future__ import annotations
import re
from typing import Optional, Union, Any, ClassVar
from collections import defaultdict
from dataclasses import dataclass, field
from scholar_flux.exceptions.path_exceptions import (
    PathNodeIndexError,
    PathNodeMapError,
    PathCombinationError,
)

from scholar_flux.utils.paths import PathSimplifier
from multiprocessing import cpu_count, get_context

from scholar_flux.utils.paths import ProcessingPath, PathNode
from scholar_flux.utils.paths.path_discoverer import PathDiscoverer
from scholar_flux.utils.paths.path_node_map import PathNodeMap
from scholar_flux.utils.paths.record_path_chain_map import RecordPathChainMap
from scholar_flux.utils import try_quote_numeric, try_call

import logging

logger = logging.getLogger(__name__)


@dataclass
class PathNodeIndex:
    """The PathNodeIndex is a dataclass that enables the efficient processing of nested key value pairs from JSON data
    commonly received from APIs providing records, articles, and other forms of data.

    This index enables the orchestration of both parsing, flattening, and the simplification of
    JSON data structures.

    Args:
        index (PathNodeMap): A dictionary of path-node mappings that are used by the PathNodeIndex to simplify JSON
                             structures into a singular list of dictionaries where each dictionary represents a record
        simplifier (PathSimplifier): A structure that enables the simplification of a path node index into a singular
                                     list of dictionary records. The structure is initially used to identify unique
                                     path names for each path-value combination.
    Class Variables:
        DEFAULT_DELIMITER (str): A delimiter to use by default when reading JSON structures and transforming the
                                 list of keys used to retrieve a terminal path into a simplified string. Each
                                 individual key is separated by this delimiter.
        MAX_PROCESSES (int): An optional maximum on the total number of processes to use when simplifying multiple
                             records into a singular structure in parallel. This can be configured directly
                             or turned off altogether by setting this class variable to None.
    Example Usage:
        >>> from scholar_flux.utils import PathNodeIndex
        >>> record_test_json: list[dict] = [
        >>>     {
        >>>         "authors": {"principle_investigator": "Dr. Smith", "assistant": "Jane Doe"},
        >>>         "doi": "10.1234/example.doi",
        >>>         "title": "Sample Study",
        >>>         # "abstract": ["This is a sample abstract.", "keywords: 'sample', 'abstract'"],
        >>>         "genre": {"subspecialty": "Neuroscience"},
        >>>         "journal": {"topic": "Sleep Research"},
        >>>     },
        >>>     {
        >>>         "authors": {"principle_investigator": "Dr. Lee", "assistant": "John Roe"},
        >>>         "doi": "10.5678/example2.doi",
        >>>         "title": "Another Study",
        >>>         "abstract": "Another abstract.",
        >>>         "genre": {"subspecialty": "Psychiatry"},
        >>>         "journal": {"topic": "Dreams"},
        >>>     },
        >>> ]
        >>> normalized_records = PathNodeIndex.normalize_records(record_test_json)
        >>> normalized_records
        # OUTPUT: [{'abstract': 'Another abstract.',
        #         'doi': '10.5678/example2.doi',
        #         'title': 'Another Study',
        #         'authors.assistant': 'John Roe',
        #         'authors.principle_investigator': 'Dr. Lee',
        #         'genre.subspecialty': 'Psychiatry',
        #         'journal.topic': 'Dreams'},
        #        {'doi': '10.1234/example.doi',
        #         'title': 'Sample Study',
        #         'authors.assistant': 'Jane Doe',
        #         'authors.principle_investigator': 'Dr. Smith',
        #         'genre.subspecialty': 'Neuroscience',
        #         'journal.topic': 'Sleep Research'}]

    """

    DEFAULT_DELIMITER: ClassVar[str] = ProcessingPath.DEFAULT_DELIMITER
    MAX_PROCESSES: ClassVar[Optional[int]] = 8
    node_map: PathNodeMap | RecordPathChainMap = field(default_factory=PathNodeMap)
    simplifier: PathSimplifier = field(
        default_factory=lambda: PathSimplifier(
            delimiter=PathNodeIndex.DEFAULT_DELIMITER, non_informative=["i", "value"]
        )
    )
    use_cache: Optional[bool] = None

    def __post_init__(self):
        """Method automatically used after initialization, to validate and set the index and simplifier.

        The index represents the preprocessed json data that has been transformed into a dictionary of path-node
        mappings whereas the validated simplifier is then used to flatten the index into a list of dictionaries.

        """
        object.__setattr__(self, "index", self._validate_index(self.node_map, self.use_cache))
        object.__setattr__(self, "simplifier", self._validate_simplifier(self.simplifier))

    @classmethod
    def _validate_simplifier(cls, simplifier: PathSimplifier) -> PathSimplifier:
        """Determine whether the argument provided to the simplifier parameter Is of type PathSimplifier.

        Args:
            simplifier (PathSimplifier): A simplifier object for normalizing records
        Raises:
            PathNodeIndexError in the event that the expected type is not a PathSimplifier

        """
        if not isinstance(simplifier, PathSimplifier):
            raise PathNodeIndexError(
                f"The argument, simplifier, expected a PathSimplifier. Received {type(simplifier)}"
            )
        return simplifier

    @classmethod
    def _validate_index(
        cls,
        node_map: Union[PathNodeMap, RecordPathChainMap, dict[ProcessingPath, PathNode]],
        use_cache: Optional[bool] = None,
    ) -> PathNodeMap | RecordPathChainMap:
        """Determine whether the current path is an index of paths and nodes.

        Args:
            node_map (dict[ProcessingPath, PathNode])
        Raises:
            PathNodeIndexError in the event that the expected type is not a dictionary of paths

        """
        if not node_map:
            return PathNodeMap(use_cache=use_cache)  # set directly if empty
        if isinstance(node_map, (PathNodeMap, RecordPathChainMap)):
            return node_map
        if isinstance(node_map, dict):
            return PathNodeMap(node_map, use_cache=use_cache)
        else:
            raise PathNodeIndexError(f"The argument, node_map, expected a PathNodeMap. Recieved {type(node_map)}")

    @classmethod
    def from_path_mappings(
        cls, path_mappings: dict[ProcessingPath, Any], chain_map: bool = False, use_cache: Optional[bool] = None
    ) -> PathNodeIndex:
        """Takes a dictionary of path:value mappings and transforms the dictionary into a list of PathNodes: useful for
        later path manipulations such as grouping and consolidating paths into a flattened dictionary.

        If use_cache is not specified, then the Mapping will use the class default to determine whether
        or not to cache.

        Returns:
            PathNodeIndex: An index of PathNodes created from a dictionary

        """

        Map = RecordPathChainMap if chain_map else PathNodeMap
        nodes = (PathNode(path, value) for path, value in path_mappings.items())
        return cls(Map(*nodes, use_cache=use_cache), use_cache=use_cache)

    def __repr__(self) -> str:
        """Helper method for simply returning the name of the current class and the count of elements in the index."""
        class_name = self.__class__.__name__
        return f"{class_name}(index(len={len(self.node_map)}))"

    def get_node(self, path: Union[ProcessingPath, str]) -> Optional[PathNode]:
        """Try to retrieve a path node with the given path.

        Args:
            The exact path of to search for in the index
        Returns:
            Optional[PathNode]: The exact node that matches the provided path.
                                Returns None if a match is not found

        """
        return self.node_map.get_node(path)

    def search(self, path: ProcessingPath) -> list[PathNode]:
        """
        Attempt to find all values with that match the provided path or have sub-paths
        that are an exact match to the provided path
        Args:
            path Union[str, ProcessingPath] the path to search for.
            Note that the provided path must match a prefix/ancestor path of an indexed path
            exactly to be considered a match
        Returns:
            dict[ProcessingPath, PathNode]: All paths equal to or containing sub-paths
                                            exactly matching the specified path
        """
        return list(self.node_map.filter(path).values())

    def pattern_search(self, pattern: Union[str, re.Pattern]) -> list[PathNode]:
        """Attempt to find all values containing the specified pattern using regular expressions
        Args:
            pattern (Union[str, re.Pattern]) pattern to search for
        Returns:
            dict[ProcessingPath, PathNode]: all paths and nodes that match the specified pattern
        """

        if not isinstance(pattern, (str, re.Pattern)):
            raise TypeError(
                "Invalid Value passed to PathIndex: expected " f"string/re.Pattern, received ({type(pattern)})"
            )
        pattern = re.compile(pattern) if not isinstance(pattern, re.Pattern) else pattern
        return [node for node in self.node_map.nodes if pattern.search(node.path.to_string()) is not None]

    def simplify_to_rows(
        self,
        object_delimiter: Optional[str] = ";",
        parallel: bool = False,
        max_components: Optional[int] = None,
        remove_noninformative: bool = True,
    ) -> list[dict[str, Any]]:
        """Simplify indexed nodes into a paginated data structure.

        Args:
            object_delimiter (str): The separator to use when collapsing multiple values into a single string.
            parallel (bool): Whether or not the simplification into a flattened structure should occur in parallel
        Returns:
            list[dict[str, Any]]: A list of dictionaries representing the paginated data structure.

        """
        sorted_nodes = sorted(self.node_map.nodes, key=lambda node: (node.path_keys, node.path))

        self.simplifier.simplify_paths(
            [node.path_group for node in sorted_nodes],
            max_components=max_components,
            remove_noninformative=remove_noninformative,
        )

        indexed_nodes = defaultdict(set)

        for node in sorted_nodes:
            indexed_nodes[node.record_index].add(node)

        node_chunks = ((node_chunk, object_delimiter) for node_chunk in indexed_nodes.values())

        if not parallel:
            return [self.simplifier.simplify_to_row(*node_chunk) for node_chunk in node_chunks]

        # Prepare data for multiprocessing

        # Use multiprocessing to process nodes in parallel
        ctx = get_context("spawn")
        max_processes = self.MAX_PROCESSES or len(list(node_chunks))
        with ctx.Pool(processes=min(cpu_count(), max_processes)) as pool:
            normalized_rows = pool.starmap(self.simplifier.simplify_to_row, node_chunks)
        return normalized_rows

    def combine_keys(self, skip_keys: Optional[list] = None) -> None:
        """Combine nodes with values in their paths by updating the paths of count nodes.

        This method searches for paths ending with values and count, identifies related nodes,
        and updates the paths by combining the value with the count node.

        Args:
            skip_keys (Optional[list]): Keys that should not be combined regardless of a matching pattern
            quote_numeric (Optional[bool]): Determines whether to quote integer components of paths to distinguish
                                            from Indices (default behavior is to quote them (ex. 0, 123).


        Raises:
            PathCombinationError: If an error occurs during the combination process.

        """
        try:
            skip_keys = skip_keys or []

            # Search for paths ending with 'values' and 'count'
            count_node_list = self.pattern_search(re.compile(r".*value(s)?.*count$"))
            node_updates = 0

            for count_node in count_node_list:
                if count_node is None or count_node.path in skip_keys:
                    logger.debug(f"Skip keys include '{count_node.path}'. Continuing...")
                    continue
                # try:
                if not count_node.path.depth > 1:
                    logger.debug(
                        f"Skipping node '{count_node}' at depth={count_node.path.depth} " "as it cannot be combined."
                    )
                    continue

                # Search for value nodes related to the count node
                value_node_pattern = (count_node.path[:-1] / "value$").to_pattern()
                value_node_list = self.pattern_search(value_node_pattern)

                if len(value_node_list) == 1:
                    value_node = value_node_list[0]

                    if value_node is None:
                        logger.debug(f"Value is None for {value_node}. Continuing...")
                        continue

                    value = try_quote_numeric(value_node.value) or value_node.value
                    if value is None:
                        logger.debug(f"Value is None for {value_node} Continuing...")
                        continue

                    # Create new path for the combined node
                    updated_count_path = value_node.path / value / "count"

                    # Update the count node path
                    updated_count_node = count_node.update(path=updated_count_path)
                    self.node_map.add(updated_count_node, overwrite=True)
                    try_call(
                        self.node_map.remove,
                        args=(value_node,),
                        suppress=(PathNodeMapError,),
                        log_level=logging.INFO,
                    )

                    # Remove the old count node
                    try_call(
                        self.node_map.remove,
                        args=(count_node,),
                        suppress=(PathNodeMapError,),
                        log_level=logging.INFO,
                    )

                    # avoid attempting to add combine newly combined nodes to prevent redundancy
                    skip_keys.append(count_node)

                    node_updates += 1

            logger.info(
                f"Combination of {node_updates} nodes successful"
                if node_updates > 0
                else "No combinations of nodes were created"
            )

        except Exception as e:
            logger.exception(f"Error during nodes combination: {e}")
            raise PathCombinationError(f"Error during nodes combination: {e}")

    @classmethod
    def normalize_records(
        cls,
        json_records: dict | list[dict],
        combine_keys: bool = True,
        object_delimiter: Optional[str] = ";",
        parallel: bool = False,
    ) -> list[dict[str, Any]]:
        """Full pipeline for processing a loaded JSON structure into a list of dictionaries where each individual list
        element is a processed and normalized record.

        Args:
            json_records (dict[str,Any] | list[dict[str,Any]]): The JSON structure to normalize. If this structure
                         is a dictionary, it will first be nested in a list as a single element before processing.
            combine_keys: bool: This function determines whether or not to combine keys that are likely to
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
        path_mappings = PathDiscoverer(record_list).discover_path_elements() if isinstance(record_list, list) else {}

        if not isinstance(path_mappings, dict) or not path_mappings:
            logger.warning(
                f"The json structure of type, {type(json_records)} contains no rows. Returning an empty list"
            )
            return []

        logger.info(f"Discovered {len(path_mappings)} terminal paths")
        path_node_index = cls.from_path_mappings(path_mappings)
        logger.info("Created path index successfully from the provided path mappings")
        if combine_keys:
            logger.info("Combining keys..")
            path_node_index.combine_keys()
        normalized_records = path_node_index.simplify_to_rows(object_delimiter=object_delimiter, parallel=parallel)
        logger.info(f"Successfully normalized {len(normalized_records)} records")
        return normalized_records

    @property
    def nodes(self) -> list[PathNode]:
        """Returns a list of PathNodes stored within the index.

        Returns:
            list[PathNode]: The complete list of all PathNodes that have been registered in the PathIndex

        """
        return self.node_map.nodes

    @property
    def paths(self) -> list[ProcessingPath]:
        """Returns a list of Paths stored within the index.

        Returns:
            list[ProcessingPath]: The complete list of all paths that have been registered in the PathIndex

        """
        return self.node_map.paths

    @property
    def record_indices(self) -> list[int]:
        """Helper property for retrieving the full list of all record indices across the current mapping of paths to
        nodes for the current index.

        This property is a helper method to quickly retrieve the full list of sorted record_indices.

        It refers back to the map for the underlying implementation in the retrieval of record_indices.

        Returns:
            list[int]: A list containing integers denoting individual records found in each path.

        """
        return self.node_map.record_indices


__all__ = ["PathNodeIndex"]
