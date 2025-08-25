# scholar_flux.utils.path_index
from __future__ import annotations
import re
from typing import Optional, Union, Any, ClassVar
from collections import defaultdict
from dataclasses import dataclass, field
from scholar_flux.exceptions.path_exceptions import (PathNodeIndexError,
                                                     PathNodeMapError,
                                                     PathCombinationError)

from scholar_flux.utils.paths import PathSimplifier
from types import GeneratorType
from multiprocessing import Pool, cpu_count

from scholar_flux.utils.paths import ProcessingPath, PathNode
from scholar_flux.utils.paths.path_discoverer import PathDiscoverer
from scholar_flux.utils.paths.path_node_map import PathNodeMap
from scholar_flux.utils import try_quote_numeric, try_call

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


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
        return f"PathNodeIndex(index(len={len(self.index)}))"

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

        if not parallel:
            return [self.simplifier.simplify_to_row(indexed_nodes[idx],collapse=object_delimiter) for idx in indexed_nodes.keys()]

        # Prepare data for multiprocessing
        node_chunks = [(node_chunk, object_delimiter) for node_chunk in indexed_nodes.values()]

        # Use multiprocessing to process nodes in parallel
        with Pool(processes=min(cpu_count(), len(node_chunks))) as pool:
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
