# /utils/paths/processing_cache.py
"""The scholar_flux.utils.paths.path_cache class implements the PathProcessingCache to cache path processing operations.

By caching terminal paths and their parent paths, the PathProcessingCache class facilitates the faster, more efficient
filtering, processing, and retrieval of nested JSON data components and structures as represented by path nodes.

For the duration that each path-node combination exists, the cache uses weakly-referenced dictionaries and
weakly-referenced sets to facilitate indexed trie operations and the process of filtering each path-node combination.

"""
from __future__ import annotations
from typing import Optional, Set, Literal
from collections import defaultdict
from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    PathCacheError,
)


from scholar_flux.utils.paths import ProcessingPath
from weakref import WeakSet, WeakKeyDictionary

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class PathProcessingCache:
    """The PathProcessingCache class implements a method of path caching that enables faster prefix searches. and
    retrieval of terminal paths associated with a path to node mapping. This class is used within PathNodeMaps and
    RecordPathNodeMaps to increase the speed and efficiency of path discovery, processing, and filtering path-node
    mappings.

    Because the primary purpose of the scholar_flux Trie-based path-node-processing implementation is the processing and
    preparation of highly nested JSON structures from API responses, the PathProcessingCache was created
    to efficiently keep track of all descendants of a terminal node with weak references and facilitate of filtering
    and flattening path-node combinations.

    Stale data is automatically removed to reduce the number of comparisons needed to retrieve terminal paths only,
    and, as a result, later steps can more efficiently filter the complete list of terminal paths with faster path
    prefix searches to facilitate processing using Path-Node Maps and Indexes when processing JSON data structures.

    """

    def __init__(self) -> None:
        """Initializes the ProcessingCache instance.

        Attributes:
            _cache (defaultdict[str, WeakSet[ProcessingPath]]):
                Underlying cache data structure that keeps track of all descendants that begin with the current prefix
                by mapping path strings to WeakSets that automatically remove ProcessingPaths when garbage collected
            updates (WeakKeyDictionary[ProcessingPath, Literal['add', 'remove']]):
                Implements a lazy caching system that only adds elements to the `_cache` when filtering and node
                retrieval is explicitly required. The implementation uses weakly referenced keys to remove cached paths
                to ensure that references are deleted when a lazy operation is no longer needed.

        """

        self._cache: defaultdict[str, WeakSet[ProcessingPath]] = defaultdict(WeakSet)  # Initialize the cache
        self.updates: WeakKeyDictionary[ProcessingPath, Literal["add", "remove"]] = WeakKeyDictionary()

    @property
    def path_cache(self) -> defaultdict[str, WeakSet[ProcessingPath]]:
        """Helper method that allows for inspection of the ProcessingCache and automatically updates the node cache
        prior to retrieval.

        Returns:
            defaultdict[str, WeakSet[ProcessingPath]]: The underlying cache used within the ProcessingCache to
                retrieve a list all currently active terminal nodes.

        """
        self.cache_update()
        return self._cache

    def lazy_add(self, path: ProcessingPath) -> None:
        """Add a path to the cache for faster prefix searches.

        Args:
            path (ProcessingPath): The path to add to the cache.

        """
        if not isinstance(path, ProcessingPath):
            raise InvalidProcessingPathError(
                f"Path must be a ProcessingPath instance. Received: {path} - type={type(path)}"
            )
        self.updates[path] = "add"

    def lazy_remove(self, path: ProcessingPath) -> None:
        """Remove a path from the cache.

        Args:
            path (ProcessingPath): The path to remove from the cache.

        """

        if not isinstance(path, ProcessingPath):
            raise PathCacheError(f"path must be a ProcessingPath instance. Received: {path} - type={type(path)}")
        self.updates[path] = "remove"

    def _add_to_cache(self, path: ProcessingPath) -> None:
        """Add a path to the cache for faster prefix searches.

        Args:
            path (ProcessingPath): The path to add to the cache.

        """
        if not isinstance(path, ProcessingPath):
            raise PathCacheError(f"path must be a ProcessingPath instance. Received: {path} - type={type(path)}")
        path_prefixes = path.get_ancestors() + [path]

        for path_prefix in path_prefixes:
            if path_prefix is None:
                raise ValueError(f"Invalid path prefix of type {type(path_prefix)}")
            self._cache[str(path_prefix)].add(path)
        logger.debug(f"Added path to cache: {path}")

    def _remove_from_cache(self, path: ProcessingPath) -> None:
        """Removes paths from the cache explicitly. Note that the weak-reference automatically removes no-longer-
        referenced paths. As a result, this method is provided when elsewhere, keys are still referenced.

        Args:
            path (ProcessingPath): The path to remove from the cache.

        """
        if not isinstance(path, ProcessingPath):
            raise PathCacheError(f"Path Cache takes a ProcessingPath as input - received {type(path)}")

        path_prefixes = path.get_ancestors() + [path]
        for path_prefix in path_prefixes:
            if path_prefix is None:
                raise ValueError(f"Invalid path prefix of type {type(path_prefix)}")
            try:
                path_string = str(path_prefix)
                self._cache[path_string].remove(path)

            except KeyError:
                logger.debug(f"Path not found in cache: {path}")
                break
            else:
                logger.debug(f"Removed path from cache: {path}")

    def _prune_cache(self) -> None:
        """Prunes empty weak-key referenced dictionary key entries from the cache. As the set is cleared.

        Args:
            path (ProcessingPath): The path to remove from the cache.

        """
        for path in list(self._cache.keys()):
            descendants = self._cache.get(path)
            if not descendants:
                self._cache.pop(path, None)

    def cache_update(self) -> None:
        """Initializes the lazy updates for the cache given the current update instructions."""
        for path, operation in self.updates.items():
            if operation == "add":
                self._add_to_cache(path)
            elif operation == "remove":
                self._remove_from_cache(path)
        self._prune_cache()
        self.updates.clear()

    def filter(
        self,
        prefix: ProcessingPath,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> Set[ProcessingPath]:
        """Filter the cache for paths with the given prefix.

        Args:
            prefix (ProcessingPath): The prefix to search for.
            min_depth (Optional[int]): The minimum depth to search for. Default is None.
            max_depth (Optional[int]): The maximum depth to search for. Default is None.
        Returns:
            Set[ProcessingPath]: A set of paths with the given prefix.

        """
        self.cache_update()

        if not isinstance(prefix, (str, ProcessingPath)):
            raise InvalidProcessingPathError(f"Key must be a Processing Path. Received: {prefix} - type={type(prefix)}")

        if (min_depth is not None and min_depth < 0) or (max_depth is not None and max_depth < 1):
            raise ValueError(
                f"Minimum and Maximum depth must be None or greater than 0 or 1, respectively. Received: min={min_depth}, max={max_depth}"
            )

        terminal_path_list = {
            path
            for path in self._cache.get(str(prefix), set())
            if path is not None
            and (min_depth is None or min_depth <= path.depth)
            and (max_depth is None or path.depth <= max_depth)
        }

        return terminal_path_list


__all__ = ["PathProcessingCache"]
