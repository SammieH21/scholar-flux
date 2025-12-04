# /utils/models/session.py
"""The scholar_flux.utils.models.session module defines the pydantic-based configuration models and BaseSessionManager
abstract base class that is a key building block in the creation of new sessions.

Classes:
    BaseSessionManager: Defines the core, abstract methods necessary to create a new session object from session
                        manager subclasses.
    CachedSessionConfig: Defines the underlying logic necessary to validate the configuration used when creating CachedSession
                         objects using a CachedSessionManager.

"""
import datetime
import importlib.util
import requests
import requests_cache
from typing import Optional, ClassVar, Literal, Any
from typing_extensions import Self
from pathlib import Path
from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict, field_validator, model_validator, Field
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.data_storage.mongodb_storage import MongoDBStorage

import logging

logger = logging.getLogger(__name__)


class BaseSessionManager(ABC):
    """An abstract base class used as a factory to create session objects.

    This base class can be extended to validate inputs to sessions and abstract the complexity of their creation

    """

    def __init__(self, *args, **kwargs) -> None:
        """Initializes BaseSessionManager subclasses given the provided arguments."""
        pass

    @abstractmethod
    def configure_session(self, *args, **kwargs) -> requests.Session | requests_cache.CachedSession:
        """Configure the session.

        Should be overridden by subclasses.

        """
        raise NotImplementedError("configure_session must be implemented by subclasses")

    @classmethod
    def get_cache_directory(cls, *args, **kwargs) -> Optional[Path]:
        """Defines defaults used in the creation of subclasses.

        Can be optionally overridden in the creation of cached session managers

        """
        raise NotImplementedError

    def __call__(self) -> requests.Session | requests_cache.CachedSession:
        """Method that makes an instantiated session manager callable, enabling the creation of new cached sessions with
        a specific configuration.

        Calls the self.configure_session() method to return the created session object.

        """
        return self.configure_session()


BACKEND_DEPENDENCIES = {
    "dynamodb": ["boto3"],
    "filesystem": [],
    "gridfs": ["pymongo"],
    "memory": [],
    "mongodb": ["pymongo"],
    "redis": ["redis"],
    "sqlite": [],
}


class CachedSessionConfig(BaseModel):
    """A helper model used to validate the inputs provided when creating a CachedSessionManager.

    This config is used to validate the inputs to the session manager prior to attempting its creation.

    """

    cache_name: str
    backend: (
        Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] | requests_cache.BaseCache
    )
    cache_directory: Optional[Path] = None
    serializer: Optional[
        str | requests_cache.serializers.pipeline.SerializerPipeline | requests_cache.serializers.pipeline.Stage
    ] = None
    expire_after: Optional[int | float | str | datetime.datetime | datetime.timedelta] = None
    user_agent: Optional[str] = None
    kwargs: dict[str, Any] = Field(default_factory=dict)
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("cache_directory", mode="before")
    def validate_cache_directory(cls, v) -> Optional[Path]:
        """Validates the cache_directory field to flag simple cases where the value is an empty string."""

        if v is None or isinstance(v, Path):
            return v

        if isinstance(v, str):
            if len(v) == 0:
                raise ValueError(f"The value provided to the cache_directory parameter ({v}) must be a non-empty Path.")
            return Path(v)

        raise ValueError(
            f"The cache_directory parameter expected a path, received a value of a different type ({type(v)})."
        )

    @field_validator("cache_name", mode="after")
    def validate_cache_name(cls, v) -> str:
        """Validates the cache_name field to flag simple cases where the value is an empty string."""
        if len(v) == 0:
            raise ValueError(f"The value provided to the cache_name parameter ({v}) must be a non-empty string.")

        if Path(v).parent != Path("."):
            raise ValueError(f"The cache_name parameter is invalid: ({v}) should not contain directory components.")

        return v.replace("./", "", 1) if v.startswith(".") else v

    @field_validator("expire_after", mode="after")
    def validate_expire_after(cls, v):
        """Validates the expire_after field to flag simple cases where numeric values below 0 are marked as invalid."""
        if isinstance(v, int) and v < 0 and not v == -1:
            raise ValueError(
                f"The provided integer for the expire_after parameter ({v}) must be greater "
                f"than 0 or equal to -1 to signify that the cache will not expire"
            )
        return v

    @field_validator("backend", mode="before")
    def validate_backend_dependency(cls, v):
        """Validates the choice of backend to and raises an error if its dependency is missing.

        If the backend has unmet dependencies, this validator will trigger a ValidationError.

        """

        if isinstance(v, requests_cache.BaseCache):
            return v

        if not isinstance(v, str) or not v:
            raise ValueError("The backend to a requests_cache.CachedSession object must be a non-empty string.")

        backend = v.lower()
        deps = BACKEND_DEPENDENCIES.get(backend)

        if deps is None:
            supported_backends = list(BACKEND_DEPENDENCIES.keys())
            logger.error(f"The specified backend is not supported by Requests-Cache: {backend}")
            raise ValueError(
                f"Requests-Cache does not support a backend by the name of {backend}.\n"
                f"Supported backends: {supported_backends}\n"
            )

        missing = [dep for dep in deps if importlib.util.find_spec(dep) is None]
        if missing:
            missing_str = ", ".join(missing)
            logger.error(f"The specified backend requires missing dependencies: {backend}")
            raise ValueError(
                f"Backend '{v}' requires missing dependencies: {missing_str}"
                "Please install them or choose a different backend."
            )
        return backend

    @classmethod
    def _default_backend_kwargs(
        cls, backend: str | requests_cache.BaseCache, kwargs: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Auto-populate kwargs with connection settings for Redis and MongoDB backends.

        References the DEFAULT_CONFIG from storage backends for consistency:
        - RedisStorage.DEFAULT_CONFIG
        - MongoStorage.DEFAULT_CONFIG

        Args:
            backend (str | requests_cache.BaseCache):
                The backend in use. Note that default backend kwargs are only used when `backend in ('redis', 'pymongo)`
            **kwargs:
                Additional keywords to be passed to the `CachedSessionManager`

        """
        # Auto-populate using storage backend defaults (single source of truth)
        backend = backend.lower() if isinstance(backend, str) else backend

        match backend:
            case "redis":
                kwargs = RedisStorage.DEFAULT_CONFIG.copy()
                logger.info("Auto-configured Redis from RedisStorage.DEFAULT_CONFIG")
                return kwargs
            case "mongodb":
                config = MongoDBStorage.DEFAULT_CONFIG.copy()
                kwargs = {"host": config["host"], "port": config["port"]}
                logger.info("Auto-configured MongoDB from MongoDBStorage.DEFAULT_CONFIG")
                return kwargs
            case _:
                return kwargs or {}

    @model_validator(mode="after")
    def validate_backend_filepath(self) -> Self:
        """Helper method for validating when file storage is a necessity vs when it's not required."""
        backend = self.backend
        cache_name = self.cache_name
        cache_directory = self.cache_directory
        cache_path = Path(self.cache_path) if self.cache_path else self.cache_path

        if backend in ("filesystem", "sqlite") and cache_directory is None:
            raise ValueError(
                f"A filepath must be specified when using the {backend} backend. "
                f"Received directory={cache_directory}, name={cache_name}"
            )

        if backend not in ("filesystem", "sqlite") and cache_directory is not None:
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
                    "and need to be created before use."
                )

        self.kwargs = self.kwargs if self.kwargs else self._default_backend_kwargs(self.backend, self.kwargs)
        return self

    @property
    def cache_path(self) -> str:
        """Helper method for retrieving the path that the cache will be written to or named, depending on the backend.

        Assumes that the cache_name is provided to the config is not `None`.

        """
        return str(self.cache_directory / self.cache_name) if self.cache_directory else self.cache_name


__all__ = ["BaseSessionManager", "CachedSessionConfig"]
