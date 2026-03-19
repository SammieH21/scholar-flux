# /data_storage/null_storage.py
"""The scholar_flux.data_storage.null_storage module implements a Null (No-Op) Storage that is used to ensure that
responses are always reprocessed when implemented."""
from __future__ import annotations
from typing import Any, Optional
from scholar_flux.data_storage.abc_storage import ABCStorage

import logging

logger = logging.getLogger(__name__)


class NullStorage(ABCStorage):
    """NullStorage is a no-op implementation of ABCStorage. This class is useful for when you want to disable storage
    without changing code logic.

    The scholar_flux package mainly implements this storage when the user turns off processing cache.

    Example:
        >>> from scholar_flux.data_storage import DataCacheManager, NullStorage
        >>> from scholar_flux.api import SearchCoordinator
        >>> null_storage = DataCacheManager.null()
        ## This implements a data cache with the null storage under the hood:
        >>> assert isinstance(null_storage.cache_storage, NullStorage)
        >>> search_coordinator = SearchCoordinator(query='History of Data Caching', cache_manager=null_storage)
        # Otherwise the same can be performed with the following:
        >>> search_coordinator = SearchCoordinator(query='History of Data Caching', cache_results = False)
        # The processing of responses will then be recomputed on the next search:
        >>> response = search_coordinator.search(page = 1)

    """

    # for compatibility with other storage backends
    DEFAULT_NAMESPACE: Optional[str] = None
    DEFAULT_RAISE_ON_ERROR: bool = False
    STORAGE_TYPE: str = "Null"

    def __init__(
        self,
        namespace: Optional[str] = None,
        ttl: None = None,
        raise_on_error: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a No-Op cache for compatibility with the `ABCStorage` base class.

        Note that `namespace`, `ttl`, `raise_on_error`, and `**kwargs` are provided for interface compatibility, and
        specifying any of these as arguments will not affect initialization.

        """
        if namespace is not None:
            logger.warning("The parameter, `namespace` is not enforced in NullStorage. Skipping.")

        if ttl is not None:
            logger.warning("The parameter, `ttl` is not enforced in NullStorage. Skipping.")

        if raise_on_error is not None:
            logger.warning("The parameter, `raise_on_error` is not enforced in NullStorage. Skipping.")

        self.namespace: Optional[str] = None
        self.ttl = None
        self.raise_on_error: bool = False

    def _initialize(self, *args: Any, **kwargs: Any) -> None:
        """Method added for abstract class consistency - no-op"""
        pass

    def clone(self) -> NullStorage:
        """Helper method for creating a new implementation of the current NullStorage."""
        cls = self.__class__
        return cls()

    def retrieve(self, *args: Any, **kwargs: Any) -> Optional[Any]:
        """Method added for abstract class consistency - no-op"""
        return None

    def retrieve_all(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        """Method added for abstract class consistency - returns a dictionary for type consistency"""
        return {}

    def retrieve_keys(self, *args: Any, **kwargs: Any) -> Optional[list[str]]:
        """Method added for abstract class consistency - returns a list for type consistency"""
        return []

    def update(self, *args: Any, **kwargs: Any) -> None:
        """Method added for abstract class consistency - no-op"""
        pass

    def delete(self, *args: Any, **kwargs: Any) -> None:
        """Method added for abstract class consistency - no-op"""
        pass

    def delete_all(self, *args: Any, **kwargs: Any) -> None:
        """Method added for abstract class consistency - no-op"""
        pass

    def verify_cache(self, *args: Any, **kwargs: Any) -> bool:
        """Method added for abstract class consistency - returns False, indicating that no cache is ever stored"""
        return False

    def verify_connection(self) -> None:
        """No-Op that otherwise raises an error when connections can't be established successfully."""
        pass

    @classmethod
    def is_available(cls, *args: Any, **kwargs: Any) -> bool:
        """
        Method added for abstract class consistency - returns True, indicating that
        the no-op storage is always available although no cache is ever stored.
        """
        return True

    def __bool__(self, *args: Any, **kwargs: Any) -> bool:
        """The NullStorage is Falsy, indicating that no cache is ever stored."""
        return False


__all__ = ["NullStorage"]
