# /sessions/session_manager.py
"""The scholar_flux.sessions.session_manager module implements the SessionManager & CachedSessionManager for requests.

These classes serve as factory methods in the creation of requests.Session objects and requests_cache.CachedSession objects.

By calling the `configure_session` method on a session manager, a new session can be created that implements basic
or cached sessions depending on which SessionManager was created.

Classes:
    SessionManager: Base class holding the configuration for non-cached sessions
    CachedSessionManager: Extensible factory class allowing users to define cached sessions with the selected backend

"""

import datetime
import requests
import requests_cache
from typing import Optional, Type, Literal, TYPE_CHECKING, Any
from pathlib import Path
import logging
from scholar_flux.package_metadata import get_default_writable_directory
from scholar_flux.exceptions.util_exceptions import (
    SessionCreationError,
    SessionConfigurationError,
    SessionInitializationError,
    CachedSessionValidationError,
    SessionCacheDirectoryError,
)
from scholar_flux.sessions.models.session import (
    BaseSessionManager,
    CachedSessionConfig,
    SessionCacheBackendType,
    SessionCacheSerializer,
    SessionCacheBackend,
)
from scholar_flux.utils import config_settings
from scholar_flux.utils.helpers import try_none
from scholar_flux.utils.repr_utils import generate_repr_from_string

from pydantic import ValidationError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    __class__: Type


class SessionManager(BaseSessionManager):
    """Manager that creates a simple requests session using the default settings and the provided User-Agent.

    Example:
        >>> from scholar_flux.sessions import SessionManager
        >>> from scholar_flux.api import SearchAPI
        >>> from requests import Session
        >>> session_manager = SessionManager(user_agent='scholar_flux_user_agent')
        ### Creating the session object
        >>> session = session_manager.configure_session()
        ### Which is also equivalent to:
        >>> session = session_manager()
        ### This implementation returns a requests.session object which is compatible with the SearchAPI:
        >>> assert isinstance(session, Session)
        # OUTPUT: True
        >>> api = SearchAPI(query='history of software design', session = session)

    """

    def __init__(self, user_agent: Optional[str] = None) -> None:
        """Initializes a basic session manager that sets the user agent if provided.

        Args:
            user_agent (Optional[str]):
                The User-Agent to be passed as a parameter in the creation of the session object. When a user_agent is
                not available, the user-agent will instead delegate the assignment of a User-Agent to the `requests`
                package (e.g., `python-requests/2.32.5`)

        """
        if user_agent is None:
            user_agent = try_none(
                config_settings.get("SCHOLAR_FLUX_DEFAULT_USER_AGENT")
            )  # 'None'/empty strings -> None

        if user_agent is not None and not (isinstance(user_agent, str) and len(user_agent) > 0):
            raise SessionCreationError(
                "Error creating the session manager: The provided user_agent parameter is not a string"
            )
        self.user_agent = user_agent

    def configure_session(self) -> requests.Session:
        """Configures a basic requests session with the provided user_agent attribute.

        Returns:
            requests.Session: a regular requests.session object with the default settings and an optional user header.

        """
        session = requests.Session()
        if self.user_agent:
            session.headers.update({"User-Agent": self.user_agent})
        logger.info("Default session successfully established.")
        return session

    @classmethod
    def with_session(cls, *, user_agent: Optional[str] = None) -> requests.Session:
        """Convenience factory method for creating and configuring a new requests.Session instance.

        Note: This method is designed to first instantiate the current SessionManager class with the specified
        User-Agent.

        Args:
            user_agent (Optional[str]): The User-Agent to be passed as a parameter when creating the session object.

        Returns:
            requests.Session: A new requests.Session object with the configured User-Agent.

        """
        session_manager = cls(user_agent=user_agent)
        return session_manager.configure_session()

    def __repr__(self) -> str:
        """Creates a string representation of the SessionManager indicating the user agent.

        Returns:
            (str): a string representation of the current SessionManager class instance.

        """
        nm = __class__.__name__
        string_representation = f"{nm}(user_agent='{self.user_agent}')"
        return string_representation


class CachedSessionManager(SessionManager):
    """This session manager is a wrapper around requests-cache and enables the creation of a requests-cache session with
    defaults that abstract away the complexity of cached session management.

    The purpose of this class is to abstract away the complexity in cached sessions by providing reasonable defaults
    that are well integrated with the scholar_flux package. The requests_cache package is built off of the base requests
    library and can similarly be injected into the scholar_flux SearchAPI for making cached queries.

    Examples:
        >>> from scholar_flux.sessions import CachedSessionManager
        >>> from scholar_flux.api import SearchAPI
        >>> from requests_cache import CachedSession
        ### creates a sqlite cached session in a package-writable directory
        >>> session_manager = CachedSessionManager(user_agent='scholar_flux_user_agent')
        >>> cached_session = session_manager() # defaults to a sqlite session in the package directory
        ### Which is equivalent to:
        >>> cached_session = session_manager.configure_session() # defaults to a sqlite session in the package directory
        >>> assert isinstance(cached_session, CachedSession)
        ### Similarly to the basic requests.session, this can be dependency injected in the SearchAPI:
        >>> SearchAPI(query = 'history of software design', session = cached_session)

    """

    DEFAULT_EXPIRE_AFTER: Optional[int] = config_settings.get("SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_TTL")

    def __init__(
        self,
        user_agent: Optional[str] = None,
        cache_name: Optional[str] = None,
        cache_directory: Optional[Path | str] = None,
        backend: Optional[SessionCacheBackendType] = None,
        serializer: Optional[SessionCacheSerializer] = None,
        expire_after: Optional[int | float | str | datetime.datetime | datetime.timedelta] = None,
        raise_on_error: bool = False,
    ) -> None:
        """Initializes the CachedSessionManager, defining and validating the options for `CachedSession` generation.

        The inputs, once validated via pydantic, are passed to the self.configure_session method to generate a session
        object.

        Args:
            user_agent (str):
                Specifies the name to use for the User-Agent parameter that is to be provided in each request header.
            cache_name (Optional[str]):
                The name to associate with the current cache - used as a file in the case of filesystem/sqlite storages,
                and is otherwise used as a cache name in the case of storages such as Redis. If not provided, the cache
                name defaults to "search_requests_cache".
            cache_directory Optional(Path | str):
                Defines the directory where the cache file is stored. if not provided, the cache_directory,
                when needed (sqlite, filesystem storage, etc.) will default to the first writable directory
                location using the `scholar_flux.package_metadata.get_default_writable_directory` method.
            backend (Optional[Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] | requests_cache.BaseCache]):
                Defines the backend to use when creating a requests-cache session. the default is sqlite.
                Other backends include `memory`, `filesystem`, `mongodb`, `redis`, `gridfs`, and `dynamodb`.

                Users can enter in direct cache storage implementations from requests_cache, including
                RedisCache, MongoCache, SQLiteCache, etc. If left `None`, the cache will default to checking
                the value of the `SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND` environment variable. If the
                environment variable is missing, the backend defaults to `sqlite`.

                For more information, visit the following link:
                https://requests-cache.readthedocs.io/en/stable/user_guide/backends.html#choosing-a-backend

            serializer: (Optional[str | requests_cache.serializers.pipeline.SerializerPipeline | requests_cache.serializers.pipeline.Stage]):
                An optional serializer that is used to prepare cached responses for storage (serialization) and deserialize them for retrieval
            expire_after (Optional[int|float|str|datetime.datetime|datetime.timedelta]):
                Sets the expiration time after which previously successfully cached responses expire. This can be
                modified via `CachedSessionManager.DEFAULT_EXPIRE_AFTER` (default=86400) unless otherwise set.
            raise_on_error (bool):
                Whether to raise an error on instantiation if an error is encountered in the creation of a session.
                If raise_on_error = False, the error is logged, and a requests.Session is created instead.

        """
        try:
            super().__init__(user_agent)

            cache_backend = (
                backend if backend is not None else self.default_session_backend(raise_on_error=raise_on_error)
            )
            session_cache_name = self.get_cache_name(cache_name)
            cache_directory = self.get_cache_directory(cache_directory, cache_backend)
            expire_after = expire_after if expire_after is not None else self._default_expire_after()

            self.config = CachedSessionConfig(
                user_agent=user_agent,
                cache_name=session_cache_name,
                cache_directory=cache_directory,
                backend=cache_backend,
                serializer=serializer,
                expire_after=expire_after,
            )
            self.raise_on_error = raise_on_error
        except (ValidationError, SessionCacheDirectoryError) as e:
            raise SessionConfigurationError(
                "Error configuring the cached session manager. "
                "At least one of the parameters provided to the "
                "CachedSessionManager is invalid:\n"
                f"{e}"
            )

    @property
    def cache_name(self) -> str:
        """Makes the config's base file name for the cache accessible by the CachedSessionManager."""
        return self.config.cache_name

    @property
    def cache_directory(self) -> Optional[Path]:
        """Makes the config's cache directory accessible by the CachedSessionManager."""
        return self.config.cache_directory

    @property
    def cache_path(self) -> str:
        """Makes the config's cache directory accessible by the CachedSessionManager."""
        return self.config.cache_path

    @property
    def backend(self) -> SessionCacheBackendType:
        """Makes the config's backend storage device for requests-cache accessible from the CachedSessionManager."""
        return self.config.backend

    @property
    def kwargs(self) -> dict[str, Any]:
        """Additional keyword arguments that can be passed to `CachedSession` on the creation of the session."""
        return self.config.kwargs

    @property
    def serializer(
        self,
    ) -> Optional[SessionCacheSerializer]:
        """Makes the serializer from the config accessible from the CachedSessionManager."""
        return self.config.serializer

    @property
    def expire_after(
        self,
    ) -> Optional[int | float | str | datetime.datetime | datetime.timedelta]:
        """Makes the config's value used for response cache expiration accessible from the CachedSessionManager."""
        return self.config.expire_after

    @classmethod
    def get_cache_name(cls, cache_name: Optional[str] = None) -> str:
        """Retrieves a valid, non-missing `cache_name` when an input for the parameter is not provided.

        When `cache_name` is None, this method attempts to retrieve a valid cache name from the
        environment variable, `SCHOLAR_FLUX_SESSION_CACHE_NAME`, when available. Otherwise, this method will
        falls back to using the default name: `search_requests_cache`.

        Args:
            cache_name (Optional[str]): The name to associate with the current session cache backend.

        Returns:
            str: The resolved cache name, either retrieved via a user-specified input, the OS environment, or the
            `search_requests_cache` default.

        """
        if cache_name is not None:
            return cache_name

        config_cache_name = try_none(config_settings.get("SCHOLAR_FLUX_SESSION_CACHE_NAME"))
        return config_cache_name if config_cache_name is not None else "search_requests_cache"

    @classmethod
    def get_cache_directory(
        cls, cache_directory: Optional[Path | str] = None, backend: Optional[SessionCacheBackendType] = None
    ) -> Optional[Path]:
        """Finds a directory path for use with session cache, favoring explicitly assigned directories if provided.

        Note that this method will only attempt to find a cache directory if one is needed, such as when
        choosing to use a "filesystem" or "sqlite" database using a string.

        Resolution order (highest to lowest priority):
            1. Explicit `cache_directory` argument
            2. `config_settings.config['CACHE_DIRECTORY']` (can be set via environment variable)
            3. Package or home directory defaults (depending on writability)

        If the resolved `cache_directory` is a string, it is coerced into a `Path` before being returned.
        Returns `None` if the backend does not require a cache directory (e.g., dynamodb, mongodb, etc.).

        Args:
            cache_directory (Optional[Path | str]): Explicit directory to use, if provided.
            backend (Optional[str | requests.BaseCache]): Backend type, used to determine if a directory is needed.

        Returns:
            Optional[Path]: The resolved cache directory as a `Path` or `None` if not applicable

        """
        if not cache_directory and (backend is None or backend in ("filesystem", "sqlite")):
            cache_directory = config_settings.get("SCHOLAR_FLUX_CACHE_DIRECTORY") or cls._default_cache_directory()

        if isinstance(cache_directory, str):
            cache_directory = Path(cache_directory)
        return cache_directory

    @classmethod
    def default_session_backend(
        cls, raise_on_error: bool = False
    ) -> Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"]:
        """Reads a default backend from `SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND` or defaulting to sqlite otherwise.

        Args:
            raise_on_error (bool):
                If True, an exception is raised when the environment variable exists but attempts
                to use an unknown requests_cache backend. If False, this method instead raises a warning
                defaulting to `sqlite` instead.

        Returns:
            str: The name of the backend to use as the default session cache.

        """
        env_variable = "SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND"
        cache_storage_type: Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] = (
            config_settings.get(env_variable) or "sqlite"
        )

        # let the validation step handle determining whether the cache exists
        if raise_on_error:
            return cache_storage_type

        if not SessionCacheBackend.get(cache_storage_type):
            error_msg = f"A cached session backend cannot be created with the environment variable '{env_variable}'."
            logger.warning(f"{error_msg}: Defaulting to the `sqlite` backend instead...")
            cache_storage_type = "sqlite"

        return cache_storage_type

    @classmethod
    def _default_cache_directory(cls) -> Path:
        """Retrieves the full path to a writable cache directory used to store session cache.

        If the directory isn't writable, a new package cache directory is created in the user's home/.scholar_flux folder.

        Returns:
            Path: The full path to the cache directory.

        """
        try:
            # Attempts to create and use the default writable package_cache directory if writable
            package_cache_directory = get_default_writable_directory("package_cache")
            logger.info("Using the following directory for cache: %s", package_cache_directory)
            return package_cache_directory

        except (PermissionError, NameError, FileNotFoundError, RuntimeError) as e:
            # Fallback to a directory in the user's home folder
            raise SessionCacheDirectoryError(f"Could not create cache directory due to an exception: {e}")

    @classmethod
    def _default_expire_after(cls) -> Optional[int | float | str | datetime.datetime | datetime.timedelta]:
        """Extracts and prepares the `expire_after` field from class/config defaults of unknown types."""
        config_expire_after = try_none(config_settings.get("SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_TTL"))
        return config_expire_after if config_expire_after is not None else try_none(cls.DEFAULT_EXPIRE_AFTER)

    def configure_session(
        self, verify_connection: bool = False
    ) -> requests.Session | requests_cache.session.CachedSession:
        """Creates and returns a new `CachedSession` using the same settings shown in the current `CachedSessionConfig`.

        Note:
            If the cached session can not be configured due to permission errors or connection errors, the
            session_manager will fallback to creating a requests.Session if the self.raise_on_error attribute
            is set to False.

        Args:
            verify_connection (bool):
                Indicates whether CachedSession validation should occur by reading from cache. Useful for verifying
                whether the cache for remote connections (redis, mongodb) is accessible and the deserialization
                pipeline is operating as intended when a serializer is specified.

        Returns:
            requests.Session | requests_cache.CachedSession:
                A cached session object if successful otherwise returns a requests.Session object
                in the event of an error.

        """
        try:
            cached_session = requests_cache.session.CachedSession(
                cache_name=self.cache_path,
                backend=self.backend,
                serializer=self.serializer,
                expire_after=self.expire_after,
                allowable_methods=("GET",),
                allowable_codes=[200],
                **self.kwargs,
            )

            if self.user_agent:
                cached_session.headers.update({"User-Agent": self.user_agent})

            if verify_connection:
                self.validate_cached_session(cached_session)

            logger.info("Cached session (%s) successfully established", self.cache_path)
            logger.info("Cache records expire after: %s seconds.", self.expire_after)
            return cached_session

        except (PermissionError, ConnectionError, OSError) as e:
            logger.error("Couldn't create cached session due to an error: %s.", e)

            if self.raise_on_error:
                raise SessionInitializationError(f"An error occurred during the creation of the CachedSession: {e}")

        logger.warning("Falling back to regular session.")
        return super().configure_session()

    @classmethod
    def with_session(
        cls,
        backend: Optional[SessionCacheBackendType] = None,
        *,
        user_agent: Optional[str] = None,
        cache_name: Optional[str] = None,
        cache_directory: Optional[Path | str] = None,
        serializer: Optional[SessionCacheSerializer] = None,
        expire_after: Optional[int | float | str | datetime.datetime | datetime.timedelta] = None,
        raise_on_error: bool = False,
        verify_connection: bool = False,
    ) -> requests.Session | requests_cache.session.CachedSession:
        """Convenience factory method for creating and configuring a new CachedSession.

        Note: For consistency with the DataCacheManager (Layer 2 processing cache), this method is designed to use the
        `backend` parameter as the only positional parameter while all others are designated as keyword only arguments.

        Args:
            backend (Optional[Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] | requests_cache.BaseCache]):
                Defines the backend to use when creating a requests-cache session. the default is sqlite. Other backends
                include `memory`, `filesystem`, `mongodb`, `redis`, `gridfs`, and `dynamodb`.
            user_agent (str):
                Specifies the name to use for the User-Agent parameter that is to be provided in each request header.
            cache_name (Optional[str]):
                The name to associate with the current cache - used as a file in the case of filesystem/sqlite storages,
                and is otherwise used as a cache name in the case of storages such as Redis.
            cache_directory Optional(Path | str):
                Defines the directory where the cache file is stored. if not provided, the cache_directory, when needed
                (sqlite, filesystem storage, etc.) will default to the first writable directory location using the
                `scholar_flux.package_metadata.get_default_writable_directory` method.
            serializer: (Optional[str | requests_cache.serializers.pipeline.SerializerPipeline | requests_cache.serializers.pipeline.Stage]):
                An optional serializer that is used to prepare cached responses for storage (serialization) and
                deserialize them for retrieval.
            expire_after (Optional[int|float|str|datetime.datetime|datetime.timedelta]):
                Sets the expiration time after which previously successfully cached responses expire. This can be
                modified via `CachedSessionManager.DEFAULT_EXPIRE_AFTER` (default=86400) unless otherwise set.
            raise_on_error (bool):
                Whether to raise an error on instantiation if an error is encountered in the creation of a session.
            verify_connection (bool):
                Indicates whether CachedSession validation should occur by reading from cache.

        Returns:
            requests.Session | requests_cache.CachedSession:
                A new session created by calling `configure_session` on the current session manager instance.

        """
        session_manager = cls(
            user_agent=user_agent,
            cache_name=cache_name,
            cache_directory=cache_directory,
            backend=backend,
            serializer=serializer,
            expire_after=expire_after,
            raise_on_error=raise_on_error,
        )
        return session_manager.configure_session(verify_connection=verify_connection)

    @classmethod
    def validate_cached_session(cls, session: requests_cache.session.CachedSession) -> None:
        """Verifies that created CachedSession objects can successfully retrieve from cache without error.

        Note: This method is useful for verifying that `Redis`/`MongoDB` backends can successfully retrieve from cache
        and whether CachedSession using serializers created from the `EncryptionPipelineSerializerFactory`
        can successfully retrieve and deserialize previously cached responses using the current secret key.

        Args:
            session (requests_cache.CachedSession):
                A session object to validate cache retrieval for. Note that if the cache is empty, this validation step
                will not raise an error.

        Raises:
            CachedSessionValidationError: If an error occurs during the validation of the cached session instance.

        """
        try:
            if not isinstance(session, requests_cache.session.CachedSession):
                raise TypeError(f"Expected a CachedSession but instead received {type(session)}")
            keys = session.cache.responses.keys()
            cache_key = next(iter(keys), None) if keys else None
            if cache_key is not None:
                session.cache.responses.get(cache_key)  # Validating via attempting to retrieve an arbitrary value
        except Exception as e:
            exc_type = e.__class__.__name__
            exc_info = f": {e}" if str(e) else ""
            err = f"CachedSession validation was unsuccessful due to the following: {exc_type}{exc_info}"
            logger.exception(err)
            raise CachedSessionValidationError(err) from e

    def __repr__(self) -> str:
        """Creates a string representation of the current CachedSessionManager.

        This representation indicates the validated configuration values that are used to create new cached sessions
        based on the defined configuration.

        Returns:
            (str): a string representation of the class

        """
        class_name = __class__.__name__
        config = dict(self.config)
        return generate_repr_from_string(class_name, config)


__all__ = ["SessionManager", "CachedSessionManager"]
