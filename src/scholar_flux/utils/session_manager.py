# /utils/session_manager.py
import datetime
import requests
import requests_cache
from typing import Dict, Any, List, Optional, Annotated, Union, Type, TYPE_CHECKING
from pathlib import Path
import logging
from scholar_flux.exceptions.util_exceptions import SessionCreationError
import scholar_flux.utils.models.session as session_models
from pydantic import ValidationError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    __class__ : Type

class SessionManager(session_models.BaseSessionManager):
    """
    Manager that creates a simple requests session using the default settings and the provided
    User-Agent.

    Args:
        user_agent: The User-Agent to be passed as a parameter in the creation of the session object

    Attributes:
        user_agent: The User-Agent to be used when sending requests when creating the session
    """
    def __init__(self, user_agent: Optional[str] = None) -> None:
        if user_agent is not None and not isinstance(user_agent, str):
            raise SessionCreationError("Error creating the session manager: The provided user_agent parameter is not a string")
        self.user_agent = user_agent

    def configure_session(self) -> requests.Session:
        """
        Configures a basic requests session with the provided user_agent attribute

        Returns:
            requests.Session: a regular requests.seession object with the default settings and an optional user header.
        """
        session = requests.Session()
        if self.user_agent:
            session.headers.update({'User-Agent': self.user_agent})
        logger.info("Default session successfully established.")
        return session
    def __repr__(self)->str:
        """
        Creates a string representation of the SessionManager indicating
        the user agent.

        Returns:
            (str): a string representation of the class
        """
        nm=__class__.__name__
        string_reprentation =  f"{nm}(user_agent='{self.user_agent}')"
        return string_reprentation

class CachedSessionManager(SessionManager):

    def __init__(self,
                 user_agent: Optional[str] = None,
                 cache_name: str = "search_requests_cache",
                 cache_directory: Optional[Path] = None,
                 backend: str = 'sqlite',
                 serializer: Optional[str | requests_cache.serializers.pipeline.SerializerPipeline | requests_cache.serializers.pipeline.Stage]=None,
                 expire_after: Optional[int | float | str | datetime.datetime | datetime.timedelta] = 86400) -> None:
        """
        This session manager is a wrapper around requests-cache and enables the
        creation of a requests-cache session with defautls that abstract away
        the complexity of session management. The initialization of the
        CachedSessionManager defines the options that are later passed to
        the configure_session method which returns a session object.

        Args:
            user_agent (str): the name to use for the User-Agent parameter provided in each request header
            cache_name (str): the name of the file that stores cached requests from the
                              requests-cache package
            cache_directory Optional(str): Defines the directory where the cache file is stored.
                                           if not provided, the package attempts to write to the
                                           package_cache folder. If a PermissionError occurs, the
                                           package attempts to write to a .scholarly_flux package in the
                                           home directory
            backend (str): Defines the backend to use when creating a requests-cache session. the default is sqlite
            serializer (Optional[str | requests_cache.serializers.pipeline.SerializerPipeline| requests_cache.serializers.pipeline.Stage]):
                                          Defines the method used
            expire_after (Optional[int|float|str|datetime.datetime|datetime.timedelta]): Sets the expiration time after which cached requests expire

        """

        try:
            super().__init__(user_agent)
            self.config = session_models.CachedSessionConfig(user_agent=user_agent,
                                                             cache_name = cache_name,
                                                             cache_directory = cache_directory or self.get_cache_directory(),
                                                             backend = backend,
                                                             serializer = serializer,
                                                             expire_after = expire_after
                                             )
        except ValidationError as e:
            raise SessionCreationError("Error creating the cached session manager. "
                                       "At least one of the parameters provided to the "
                                       "CachedSessionManager is invalid:\n"
                                       f"{e}")

    @property
    def cache_name(self)-> str:
        """Makes the config's base file name for the cache  accessible by the CachedSessionManager"""
        return self.config.cache_name

    @property
    def cache_directory(self) -> Path:
        """Makes the config's cache directory accessible by the CachedSessionManager"""
        return self.config.cache_directory

    @property
    def backend(self) -> str:
        """Makes the config's backend storage device for requests-cache accessible from the CachedSessionManager"""
        return self.config.backend

    @property
    def serializer(self) -> Optional[str | requests_cache.serializers.pipeline.SerializerPipeline | requests_cache.serializers.pipeline.Stage]:
        """Makes the serializer from the config accessible from the CachedSessionManager"""
        return self.config.serializer

    @property
    def expire_after(self) -> Optional[int | float | str | datetime.datetime | datetime.timedelta]:
        """Makes the config's value used for response cache expiration accessible from the CachedSessionManager"""
        return self.config.expire_after

    @classmethod
    def get_cache_directory(cls, subdirectory: Path | str = Path("data") / "package_cache") -> Path :
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
            cache_directory = Path(session_models.__file__).parent.parent.parent / subdirectory

            # ensure that the scholar_flux package exists prior to attempting to create the
            # cache directory
            if not cache_directory.parent.exists():
                raise FileNotFoundError

            # cache_directory = Path(__file__).resolve().parent.parent / subdirectory
            cache_directory.mkdir(parents=True, exist_ok=True)
            return cache_directory

        except (PermissionError, NameError, FileNotFoundError):
            # Fallback to a directory in the user's home folder
            home_cache_directory = Path.home() / '.scholar_flux' / subdirectory
            try:
                home_cache_directory.mkdir(parents=True, exist_ok=True)
                logger.info("Using home directory for cache: %s", home_cache_directory)
                return home_cache_directory
            except (PermissionError, NameError, FileNotFoundError) as e:
                logger.error("Failed to create cache directory in home: %s", e)
                # Handle further or raise an exception to inform the user
                raise ValidationError(f"Could not create cache directory due to an exception: {e}")

    def configure_session(self) -> requests.Session | requests_cache.CachedSession:
        """
        Configures and returns a cached session object with the options provided to the config
        when creating the CachedSessionManager. In the event of an error, this definition will
        fall back to using a regular session object.

        Returns:
            requests.Session | requests_cache.CachedSession: a cached session object if successful
                                                             otherwise returns a regular requests object
                                                             in the event of an error.
        """
        try:
            cache_file = self.cache_directory / self.cache_name

            cached_session = requests_cache.CachedSession(
                cache_name=str(cache_file),
                backend=self.backend,
                serializer=self.serializer,
                expire_after=self.expire_after,
                allowable_methods=('GET',),
                allowable_codes=[200],
            )

            if self.user_agent:
                cached_session.headers.update({'User-Agent': self.user_agent})

            logger.info("Cached session successfully established at: %s", cache_file)
            logger.info("Cache records expire after: %s seconds.", self.expire_after)
            return cached_session
        except SessionCreationError as e:
            logger.error("Couldn't create cached session due to an error: %s. Falling back to regular session.", e)

        return super().configure_session()

    def __repr__(self)-> str:
        """
        Creates a string representation of the CachedSessionManager indicating the configuration
        values that instantiate the CachedSessionConfig which will be used to create the session.

        Returns:
            (str): a string representation of the class
        """
        nm=__class__.__name__

        indent=" " * (len(nm)+1)
        sep = f",\n{indent}"
        config = f"{sep}".join(f"{option}={value}" for option, value in self.config.model_dump().items())

        string_reprentation = f"{nm}(config={config})"
        return string_reprentation
