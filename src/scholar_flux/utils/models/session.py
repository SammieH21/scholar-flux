# /utils/models/session.py
import datetime
import requests
import requests_cache
from typing import Dict, Any, List, Optional, Annotated, Union, ClassVar
from pathlib import Path
from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict

class BaseSessionManager(ABC):
    """
    An abstract base class used as a factory to create session objects:
        This can be extended to both validate inputs to sessions and abstract
        the complexity of their creation
    """
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def configure_session(self, *args, **kwargs)-> requests.Session | requests_cache.CachedSession:
        """
        Configure the session. Should be overridden by subclasses.
        """
        raise NotImplementedError("configure_session must be implemented by subclasses")

    @classmethod
    def get_cache_directory(cls) -> Optional[Path]:
        """
        Defines defaults used in the creation of subclasses.
        Can be optionally overridden in the creation of cached session managers
        """
        raise NotImplementedError

    def __call__(self) -> requests.Session | requests_cache.CachedSession:
        """
        Method that makes the session manager callable in the creation of the session
        Calls the self.configure_session() method to return the created session object
        """
        return self.configure_session()

class CachedSessionConfig(BaseModel):
    """
    A helper model used to validate the inputs provided when creating a CachedSessionManager
    This config is used to validate the inputs to the session manager prior to attempting its creation
    """
    user_agent: Optional[str]
    cache_name: str
    cache_directory: Path
    backend: str
    serializer: Optional[str | requests_cache.serializers.pipeline.SerializerPipeline | requests_cache.serializers.pipeline.Stage]
    expire_after: Optional[int | float | str | datetime.datetime | datetime.timedelta]
    model_config: ClassVar[ConfigDict]  = ConfigDict(arbitrary_types_allowed=True)
