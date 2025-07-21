from typing import Any, List, Dict, Union, Optional
from scholar_flux.exceptions import StorageCacheException
import logging
logger = logging.getLogger(__name__)
from scholar_flux.data_storage.base import BaseStorage


class InMemoryStorage(BaseStorage):
    """
    BaseStorage class implements an in memory cache with dictionaries.

    This class provides methods to check the cache, delete from the cache,
            update the cache with new data, and retrieve data from the cache storage.
    """
    def __init__(self) -> None:
        self._initialize()

    def _initialize(self,**kwargs) -> None:
        logger.debug("Initializing in-memory cache...")
        self.cache_storage: dict = {} | kwargs

    def retrieve(self,key:str) -> Optional[Any]:
        return self.cache_storage.get(key)

    def retrieve_all(self) -> Optional[Dict[str,Any]]:
        return self.cache_storage

    def retrieve_keys(self)-> Optional[List[str]]:
        return list(self.cache_storage.keys()) or []

    def update(self,key:str,data:Any) -> None:
        self.cache_storage[key] = data

    def delete(self,key: str) -> None:
            del(self.cache_storage[key])
            logger.debug(f"Key: {key} deleted successfuly")

    def delete_all(self) -> None:
        logger.debug(f"deleting all record within cache...")

        try:
            n = len(self.cache_storage)
            self.cache_storage.clear()
            logger.debug(f"Deleted {n} records.")
        except Exception as e:
            logger.warning(f"An error occured deleting e: {e}")

    def verify_cache(self,key: str) -> bool:
        if not key:
            raise ValueError(f"Key invalid. Received {key}")
        return key in self.cache_storage
