from typing import Any, List, Dict, Union, Optional
from abc import ABC, abstractmethod
from scholar_flux.data_storage.base import BaseStorage

import logging
logger = logging.getLogger(__name__)

from typing import Any, Dict, List, Optional

class NullStorage(BaseStorage):
    """
    NullStorage is a no-op implementation of BaseStorage.
    Useful when you want to disable storage without changing code logic.
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

    def __bool__(self, *args, **kwargs) -> bool:
        return False
