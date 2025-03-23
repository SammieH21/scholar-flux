import requests
import requests_cache
from typing import Dict, Any, List, Optional, Annotated
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class BaseSessionManager:
    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent



    def configure_session(self):
        """
        Configure the session. Should be overridden by subclasses.
        """
        raise NotImplementedError("configure_session must be implemented by subclasses")

class DefaultSessionManager(BaseSessionManager):
    def configure_session(self):
        session = requests.Session()
        if self.user_agent:
            session.headers.update({'User-Agent': self.user_agent})
        logger.info("Default session successfully established.")
        return session

    def get_cache_directory(self):
        raise NotImplementedError

class CachedSessionManager(BaseSessionManager):
    def __init__(self, user_agent: Optional[str] = None, cache_name: str = "search_requests_cache",
                 cache_directory: Optional[Path] = None, backend: str = 'sqlite', serializer=None,
                 expire_after: int = 86400):
        super().__init__(user_agent)
        self.cache_name = cache_name
        self.cache_directory = cache_directory
        self.backend = backend
        self.serializer = serializer
        self.expire_after = expire_after

    def get_cache_directory(self,subdirectory=Path("data") / "cache"):
        """
        Get the full path to a cache directory within the package.
        If the directory isn't writeable, create a cache directory in the users home folder
        
        Parameters:
        - subdirectory (str): The name of the cache directory within the package.

        Returns:
        - Path: The full path to the cache directory.

        """
        
        try:
            # Attempt to create the cache directory within the package
            cache_directory = Path(__file__).resolve().parent.parent / subdirectory
            cache_directory.mkdir(parents=True, exist_ok=True)
            return cache_directory
        
        except PermissionError:
            # Fallback to a directory in the user's home folder
            home_cache_directory = Path.home() / '.scholarly_explorer' / subdirectory
            try:
                home_cache_directory.mkdir(parents=True, exist_ok=True)
                logger.info("Using home directory for cache: %s", home_cache_directory)
                return home_cache_directory
            except PermissionError as e:
                logger.error("Failed to create cache directory in home: %s", e)
                # Handle further or raise an exception to inform the user
                raise ValueError("Could not create cache directory due to permission issues.")




    def configure_session(self):
        try:
            directory = self.cache_directory or self.get_cache_directory()
            cache_file = directory / self.cache_name

            session = requests_cache.CachedSession(
                cache_name=str(cache_file),
                backend=self.backend,
                serializer=self.serializer,
                expire_after=self.expire_after,
                allowable_methods=('GET',),
                allowable_codes=[200],
            )
            logger.info("Cached session successfully established at: %s", cache_file)
            logger.info("Cache records expire after: %s seconds.", self.expire_after)
        except Exception as e:
            logger.error("Couldn't create cached session due to an error: %s. Falling back to regular session.", e)
            session = requests.Session()

        if self.user_agent:
            session.headers.update({'User-Agent': self.user_agent})
        return session

