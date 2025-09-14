from typing import Any, List, Dict, Optional
from scholar_flux.data_storage.abc_storage import ABCStorage

import logging

logger = logging.getLogger(__name__)


class NullStorage(ABCStorage):
    """
    NullStorage is a no-op implementation of ABCStorage.
    This class is useful for when you want to disable storage without changing code logic.

    The scholar_flux package mainly implements this storage when the user turns off processing
    cache.

    Example:
        >>> from scholar_flux.data_storage import DataCacheManager, NullStorage
        >>> from scholar_flux.api import SearchCoordinator
        >>> null_storage = DataCacheManager.null()
        ## This implements a data cache with the null storage under the hood:
        >>> assert isinstance(null_storage.cache_storage, NullStorage)
        >>> search_coordinator = SearchCoordinator(query='History of Data Caching', cache_manager=null_storage)
        # Otherwise the same can be performed with the following:
        >>> search_coordinator = SearchCoordinator(query='History of Data Caching', cache_results = False)
        # The processing of responses will then be recomputed - useful for trying different processing methods
        >>> response = search_coordinator.search(page = 1)
    """

    def _initialize(self, *args, **kwargs) -> None:
        pass

    def retrieve(self, *args, **kwargs) -> Optional[Any]:
        return None

    def retrieve_all(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return {}

    def retrieve_keys(self, *args, **kwargs) -> Optional[List[str]]:
        return []

    def update(self, *args, **kwargs) -> None:
        pass

    def delete(self, *args, **kwargs) -> None:
        pass

    def delete_all(self, *args, **kwargs) -> None:
        pass

    def verify_cache(self, *args, **kwargs) -> bool:
        return False

    @classmethod
    def is_available(cls, *args, **kwargs) -> bool:
        """Helper method that returns False, indicating that this class does not cache data"""
        return False

    def __bool__(self, *args, **kwargs) -> bool:
        return False
