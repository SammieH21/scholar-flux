# /sessions/models/session.py
"""The scholar_flux.session.models.session module defines basic models used for CachedSessionManager configuration.

This module defines the `BaseSessionManager` which specifies the methods to be implemented by the `SessionManager` and
`CachedSessionManager` subclasses while the `CachedSessionConfig` uses pydantic-based configuration models to validate
the creation of `CachedSessionManager` instances.

Classes:
    BaseSessionManager:
        Defines the core, abstract methods necessary to create a new session object from session manager subclasses.
    CachedSessionConfig:
        Defines the underlying logic necessary to validate the configuration used when creating CachedSession objects
        using a CachedSessionManager.

"""
from __future__ import annotations

import datetime  # noqa: TCH003
import importlib.util
import requests
import requests_cache
from enum import Enum
from typing import Any, ClassVar, Optional, Literal
from typing_extensions import Self, TypeAliasType
from pathlib import Path
from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict, field_validator, model_validator, Field
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.data_storage.mongodb_storage import MongoDBStorage
from scholar_flux.utils.helpers import parse_iso_timestamp, coerce_numeric

import logging

logger = logging.getLogger(__name__)


SessionCacheBackendType = TypeAliasType(
    "SessionCacheBackendType",
    requests_cache.backends.base.BaseCache
    | Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"],
)
SessionCacheSerializer = TypeAliasType(
    "SessionCacheSerializer",
    str | requests_cache.serializers.pipeline.SerializerPipeline | requests_cache.serializers.pipeline.Stage,
)


class SessionCacheBackend(str, Enum):
    """Known session cache backends compatible with `requests-cache`."""

    DYNAMODB = "dynamodb"
    FILESYSTEM = "filesystem"
    GRIDFS = "gridfs"
    MEMORY = "memory"
    MONGODB = "mongodb"
    REDIS = "redis"
    SQLITE = "sqlite"

    @classmethod
    def get(cls, backend: str | SessionCacheBackend) -> SessionCacheBackend | None:
        """Helper method for retrieving a known, valid requests-cache backend."""
        try:
            return cls(backend)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _missing_(cls, value: object) -> SessionCacheBackend | None:
        """Normalizes the name of the backend when lookup fails."""
        if not isinstance(value, str):
            return None
        return next((backend for backend in cls if value.lower() == backend.value), None)


BACKEND_DEPENDENCIES: dict[SessionCacheBackend, list[str]] = {
    SessionCacheBackend.DYNAMODB: ["boto3"],
    SessionCacheBackend.FILESYSTEM: [],
    SessionCacheBackend.GRIDFS: ["pymongo"],
    SessionCacheBackend.MEMORY: [],
    SessionCacheBackend.MONGODB: ["pymongo"],
    SessionCacheBackend.REDIS: ["redis"],
    SessionCacheBackend.SQLITE: [],
}


class BaseSessionManager(ABC):
    """An abstract base class used as a factory to create session objects.

    This base class can be extended to validate inputs to sessions and abstract the complexity of their creation

    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes BaseSessionManager subclasses given the provided arguments."""
        pass

    @abstractmethod
    def configure_session(self, *args: Any, **kwargs: Any) -> requests.Session | requests_cache.session.CachedSession:
        """Configure the session.

        Should be overridden by subclasses.

        """
        raise NotImplementedError("The `configure_session` method must be implemented by subclasses")

    @classmethod
    def get_cache_directory(cls, *args: Any, **kwargs: Any) -> Optional[Path]:
        """Defines defaults used in the creation of subclasses.

        Can be optionally overridden in the creation of cached session managers

        """
        raise NotImplementedError("The `get_cache_directory` method must be implemented by subclasses")

    def __call__(self, *args: Any, **kwargs: Any) -> requests.Session | requests_cache.session.CachedSession:
        """Method that makes an instantiated session manager callable, enabling the creation of new cached sessions with
        a specific configuration.

        Calls the self.configure_session() method to return the created session object.

        Args:
            *args: Positional arguments to pass to `configure_session()` if implemented.
            **kwargs: Keyword arguments to pass to `configure_session()` if implemented.

        Returns:
            requests.Session | CachedSession: A newly created session instance.

        """
        return self.configure_session(*args, **kwargs)

    @classmethod
    def with_session(cls, *args: Any, **kwargs: Any) -> requests.Session | requests_cache.session.CachedSession:
        """Convenience factory method for creating and configuring a new session instance.

        Note: This method is designed to first instantiate the current SessionManager class using the provided
        positional or keyword arguments. Subclasses can define the exact parameters and type annotations required for
        instantiation if needed.

        Args:
            *args: Positional arguments to pass to the `__init__` method of the current class
            **kwargs: Keyword arguments to pass to the `__init__` method of the current class

        Returns:
            requests.Session | CachedSession:
                A new session created by calling `configure_session` on the current session manager instance.

        """
        session_manager = cls(*args, **kwargs)
        return session_manager.configure_session()


class CachedSessionConfig(BaseModel):
    """A helper model used to validate the inputs provided when creating a CachedSessionManager.

    This config is used to validate the inputs to the session manager prior to attempting its creation.

    """

    cache_name: str
    backend: SessionCacheBackendType
    cache_directory: Optional[Path] = None
    serializer: Optional[SessionCacheSerializer] = None
    expire_after: Optional[int | float | str | datetime.datetime | datetime.timedelta] = None
    user_agent: Optional[str] = None
    kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("cache_directory", mode="before")
    def validate_cache_directory(cls, v: Optional[Path | str]) -> Optional[Path]:
        """Validates the cache_directory field to flag simple cases where the value is an empty string."""

        if v is None or isinstance(v, Path):
            return v

        if isinstance(v, str):
            if len(v) == 0:
                raise ValueError(
                    f"The value provided to the cache_directory parameter ('{v}') must be a non-empty Path."
                )
            return Path(v)

        raise ValueError(
            f"The cache_directory parameter expected a path, received a value of a different type ({type(v)})."
        )

    @field_validator("cache_name", mode="after")
    def validate_cache_name(cls, v: str) -> str:
        """Validates the cache_name field to flag simple cases where the value is an empty string."""
        if len(v) == 0:
            raise ValueError(f"The value provided to the cache_name parameter ('{v}') must be a non-empty string.")

        if Path(v).parent != Path("."):
            raise ValueError(f"The cache_name parameter is invalid: ({v}) should not contain directory components.")

        return v.replace("./", "", 1) if v.startswith(".") else v

    @field_validator("expire_after", mode="after")
    def validate_expire_after(
        cls, v: Optional[str | int | float | datetime.datetime | datetime.timedelta]
    ) -> Optional[int | float | datetime.datetime | datetime.timedelta]:
        """Validates the expire_after field to flag simple cases where numeric values below 0 are marked as invalid."""
        # convert ISO dates into timestamps when possible. This returns as a datetime object:
        if isinstance(v, str) and (expire_after_date := parse_iso_timestamp(v)) is not None:
            return expire_after_date

        if isinstance(v, (int, str, float)) and (expire_after_seconds := coerce_numeric(v)) is not None:
            # Account for raw integers (before conversion) and floats (after conversion)
            no_expiration = v == -1 or expire_after_seconds == -1.0
            if expire_after_seconds < 0 and not no_expiration:
                raise ValueError(
                    f"The provided integer for the expire_after parameter ({v}) must be greater "
                    "than 0 or equal to -1 to signify that the cache should not expire."
                )
            return None if no_expiration else (expire_after_seconds)

        # for all other strings that aren't valid timestamps
        if isinstance(v, str):
            raise ValueError(
                f"Received an invalid string for the expire_after parameter ({v}). The string could not be "
                "successfully converted into a date nor a valid numeric TTL value."
            )
        return v

    @field_validator("backend", mode="before")
    def validate_backend_dependency(cls, v: str | SessionCacheBackendType) -> SessionCacheBackendType:
        """Validates the choice of backend to and raises an error if its dependency is missing.

        If the backend has unmet dependencies, this validator will trigger a ValidationError.

        Args:
            v (str | Optional[Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] | requests_cache.BaseCache])):
                A valid backend for requests_cache (not case sensitive)

        Returns:
            Optional[Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] | requests_cache.BaseCache]):
                A BaseCache or name of a backend supported by `requests-cache`

        """

        if isinstance(v, requests_cache.backends.base.BaseCache):
            return v

        if not isinstance(v, str) or not v:
            raise ValueError("The backend to a requests_cache.CachedSession object must be a non-empty string.")

        if (backend := SessionCacheBackend.get(v)) is None:
            supported_backends = [supported_backend.value for supported_backend in SessionCacheBackend]
            logger.error(f"The specified backend is not supported by Requests-Cache: {backend}")
            raise ValueError(
                f"Requests-Cache does not support a backend by the name of {v}.\n"
                f"Supported backends: {supported_backends}\n"
            )

        missing = [dep for dep in BACKEND_DEPENDENCIES.get((backend), []) if importlib.util.find_spec(dep) is None]

        if missing:
            missing_str = ", ".join(missing)
            logger.error(f"The specified backend requires missing dependencies: {backend}")
            raise ValueError(
                f"Backend '{backend.lower()}' requires missing dependencies: {missing_str}. "
                "Please install them or choose a different backend."
            )
        return backend.value

    @classmethod
    def _add_default_backend_kwargs(
        cls, backend: str | SessionCacheBackendType, kwargs: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Auto-populate kwargs with connection settings for Redis and MongoDB backends.

        References the get_default_config() from storage backends for consistency:
        - RedisStorage.get_default_config()
        - MongoStorage.get_default_config()

        Args:
            backend (str | Optional[Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] | requests_cache.BaseCache]):
                The backend in use. Note that default backend kwargs are only used when `backend in ('redis', 'pymongo)`
            kwargs (dict[str, Any]):
                Additional keywords to be used by the `CachedSessionManager`

        Returns:
            dict[str, Any]:
                The updated dictionary of keyword arguments to use when creating a CachedSession,
                including the default host and port for Redis/MongoDB when not available.

        """
        # Auto-populate using storage backend defaults (single source of truth)
        backend = backend.lower() if isinstance(backend, str) else backend
        connection_keys = ("host", "port")
        update_kwargs: dict[str, Any] = kwargs if isinstance(kwargs, dict) else {}

        match backend:
            case "redis":
                default_connection_kwargs: dict[str, Any] = {
                    key: value for key, value in RedisStorage.get_default_config().items() if key in connection_keys
                }
                logger.info("Auto-configured Redis from RedisStorage.get_default_config()")
                return default_connection_kwargs | update_kwargs
            case "mongodb":
                default_connection_kwargs = {
                    key: value for key, value in MongoDBStorage.get_default_config().items() if key in connection_keys
                }
                logger.info("Auto-configured MongoDB from MongoDBStorage.get_default_config()")
                return default_connection_kwargs | update_kwargs
            case _:
                return update_kwargs

    @model_validator(mode="after")
    def validate_backend_filepath(self) -> Self:
        """Helper method for validating when file storage is a necessity vs when it's not required."""
        backend = self.backend
        cache_name = self.cache_name
        cache_directory = self.cache_directory
        cache_path = Path(self.cache_path) if self.cache_path else self.cache_path

        if backend in (SessionCacheBackend.FILESYSTEM, SessionCacheBackend.SQLITE) and cache_directory is None:
            raise ValueError(
                f"A filepath must be specified when using the {backend} backend. "
                f"Received directory={cache_directory}, name={cache_name}"
            )

        if backend not in (SessionCacheBackend.FILESYSTEM, SessionCacheBackend.SQLITE) and cache_directory is not None:
            logger.warning(f"Note that the cache_directory will not be used when using the {backend} backend")
            self.cache_directory = None
        else:
            logger.debug(
                f"When initialized, the Cached Session Configuration will use the {backend} "
                f"backend and the path: {cache_path}."
            )
            if isinstance(cache_path, Path) and not cache_path.parent.exists():
                logger.warning(
                    f"Warning: The parent directory, {cache_path.parent}, does not exist "
                    "and needs to be created before use."
                )

        self.kwargs = self._add_default_backend_kwargs(self.backend, self.kwargs)
        return self

    @property
    def cache_path(self) -> str:
        """Helper method for retrieving the path that the cache will be written to or named, depending on the backend.

        Assumes that the cache_name is provided to the config is not `None`.

        """
        return str(self.cache_directory / self.cache_name) if self.cache_directory else self.cache_name


__all__ = [
    "BaseSessionManager",
    "SessionCacheBackend",
    "CachedSessionConfig",
    "SessionCacheBackendType",
    "SessionCacheSerializer",
]
