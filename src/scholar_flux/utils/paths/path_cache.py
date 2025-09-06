# scholar_flux.utils.path_cache
from __future__ import annotations
from typing import Optional, Set
from collections import defaultdict
from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    PathCacheError,
)


from scholar_flux.utils.paths import ProcessingPath
from weakref import WeakSet

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ProcessingCache:
    """
    A cache for storing Processing paths for faster prefix searches.
    """

    def __init__(self) -> None:
        """
        Initializes the ProcessingCache instance
        """

        self._cache: defaultdict[str, WeakSet[ProcessingPath]] = defaultdict(WeakSet)  # Initialize the cache
        self.updates: dict[ProcessingPath, str] = {}

    def lazy_add(self, path: ProcessingPath) -> None:
        """
        Add a path to the cache for faster prefix searches.
        Args:
            path (ProcessingPath): The path to add to the cache.
        """
        if not isinstance(path, ProcessingPath):
            raise InvalidProcessingPathError(
                f"Path must be a ProcessingPath instance. Received: {path} - type={type(path)}"
            )
        self.updates[path] = "add"

    def lazy_remove(self, path: ProcessingPath) -> None:
        """
        Remove a path from the cache.
        Args:
            path (ProcessingPath): The path to remove from the cache.
        """

        if not isinstance(path, ProcessingPath):
            raise PathCacheError(f"path must be a ProcessingPath instance. Received: {path} - type={type(path)}")
        self.updates[path] = "remove"

    def _add_to_cache(self, path: ProcessingPath) -> None:
        """
        Add a path to the cache for faster prefix searches.
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
        """
        Remove a path from the cache.
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
                self._cache[str(path_prefix)].remove(path)
            except KeyError:
                logger.debug(f"Path not found in cache: {path}")
            else:
                logger.debug(f"Removed path from cache: {path}")

    def cache_update(self) -> None:
        """
        Initializes the lazy updates for the cache given the current update instructions.
        """
        for path, operation in self.updates.items():
            if operation == "add":
                self._add_to_cache(path)
            elif operation == "remove":
                self._remove_from_cache(path)
        self.updates.clear()

    def filter(
        self,
        prefix: ProcessingPath,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> Set[ProcessingPath]:
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
