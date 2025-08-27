from typing import Any, List, Dict, Optional
from abc import ABC, abstractmethod
from scholar_flux.utils.repr_utils import generate_repr

import logging
logger = logging.getLogger(__name__)

class ABCStorage(ABC):
    """
    The ABCStorage class provides the basic structure required to implement
    the data storage cache with customized backend.

    This subclasss provides methods to check the cache, delete from the cache,
            update the cache with new data, and retrieve data from the cache storage.
    """
    def __init__(self, *args,**kwargs) -> None:
        self.namespace: Optional[str] = None

    def _initialize(self,*args,**kwargs) -> None:
        """Optional base method to implement for initializing/reinitializing connections"""
        pass

    @abstractmethod
    def retrieve(self,*args,**kwargs) -> Optional[Any]:
        """Core method for retrieving a page of records from the cache"""
        raise NotImplementedError

    @abstractmethod
    def retrieve_all(self,*args,**kwargs) -> Optional[Dict[str,Any]]:
        """Core method for retrieving all pages of records from the cache"""
        raise NotImplementedError

    @abstractmethod
    def retrieve_keys(self,*args,**kwargs)-> Optional[List[str]]:
        """Core method for retrieving all keys from the cache"""
        raise NotImplementedError

    @abstractmethod
    def update(self,*args,**kwargs) -> None:
        """Core method for updating the cache with new records"""
        raise NotImplementedError

    @abstractmethod
    def delete(self,*args,**kwargs) -> None:
        """Core method for deleting a page from the cache"""
        raise NotImplementedError

    @abstractmethod
    def delete_all(self,*args,**kwargs) -> None:
        """Core method for deleting all pages of records from the cache"""
        raise NotImplementedError

    @abstractmethod
    def verify_cache(self,*args,**kwargs) -> bool:
        """Core method for verifying the cache based on the key"""
        raise NotImplementedError

    def _prefix(self, key: str) -> str:
        """
        prefixes a namespace to the given `key`:
        This method is useful for when you are using a single redis/mongodb server
            and also need to retrieve a subset of articles for a particular task.
        Args:
            key (str) The key to prefix with a namespace (Ex. CORE_PUBLICATIONS)
        Returns:
            str: The cache key prefixed with a namespace (Ex. f'CORE_PUBLICATIONS:{key}')
       """
        if not key:
            raise KeyError(f"No valid value provided for key {key}")
        if not self.namespace:
            return key
        return f"{self.namespace}:{key}" if not key.startswith(f'{self.namespace}:') else key


    def __repr__(self) -> str:
        """
        Method for indentifying the current implementation and subclasses of the BaseStoarge.
        Useful for showing the options being used to store and retrieve data stored as cache.
        """
        return generate_repr(self)
