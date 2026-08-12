# /data_storage/redis_storage.py
"""The scholar_flux.data_storage.redis_storage module implements the RedisStorage backend for the DataCacheManager.

This class implements the abstract methods required for compatibility with the scholar_flux.DataCacheManager.

This class implements caching by using the serialization-deserialization and caching features available in Redis
to store ProcessedResponse fields within the database for later CRUD operations.

WARNING: Ensure that the 'namespace' parameter is set to a non-empty, unique value for each logical cache.
Using an empty or shared namespace may result in accidental deletion or overwriting of unrelated data. For that reason,
the `delete_all` method does not perform any deletions unless a namespace exists

"""

from __future__ import annotations
from scholar_flux.exceptions import (
    RedisImportError,
    StorageCacheException,
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
)
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.utils.encoder import JsonDataEncoder
from scholar_flux.utils import config_settings  # provides the loaded global environment configuration
from scholar_flux.utils.settings_utils import SettingsDict
from scholar_flux.utils.helpers import coerce_int, try_none
from scholar_flux.security.utils import SecretUtils
from typing import Any, cast, TYPE_CHECKING

import logging
import threading

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import redis
    from redis.exceptions import RedisError, ConnectionError, TimeoutError
else:
    try:
        import redis
        from redis.exceptions import RedisError, ConnectionError, TimeoutError
    except ImportError:
        redis = None
        RedisError = Exception
        TimeoutError = Exception
        ConnectionError = Exception


class RedisStorage(ABCStorage):
    """Implements the storage methods necessary to interact with Redis using a unified backend interface.

    The RedisStorage implements the abstract methods from the ABCStorage class for use with the DataCacheManager.
    This implementation is designed to use a key-value store as a cache by which data can be stored and
    retrieved in a relatively straightforward manner similar to the In-Memory Storage.

    Examples:
        >>> from scholar_flux.data_storage import RedisStorage
        # Defaults to connecting to locally (localhost) on the default port for Redis services (6379)
        # Verifies that a Redis service is locally available.
        >>> assert RedisStorage.is_available()
        >>> redis_storage = RedisStorage(namespace='testing_functionality')
        >>> print(redis_storage)
        # OUTPUT: RedisStorage(...)
        # Adding records to the storage
        >>> redis_storage.update('record_page_1', {'id':52, 'article': 'A name to remember'})
        >>> redis_storage.update('record_page_2', {'id':55, 'article': 'A name can have many meanings'})
        # Revising and overwriting a record
        >>> redis_storage.update('record_page_2', {'id':53, 'article': 'A name has many meanings'})
        >>> redis_storage.retrieve_keys() # retrieves all current keys stored in the cache under the namespace
        # OUTPUT: ['testing_functionality:record_page_1', 'testing_functionality:record_page_2']
        >>> redis_storage.retrieve_all() # Will also be empty
        # OUTPUT: {'testing_functionality:record_page_1': {'id': 52,
        #           'article': 'A name to remember'},
        #          'testing_functionality:record_page_2': {'id': 53,
        #           'article': 'A name has many meanings'}}
        >>> redis_storage.retrieve('record_page_1') # retrieves the record for page 1
        # OUTPUT: {'id': 52, 'article': 'A name to remember'}
        >>> redis_storage.delete_all() # deletes all records from the namespace
        >>> redis_storage.retrieve_keys() # Will now be empty
        >>> redis_storage.retrieve_all() # Will also be empty

    """

    DEFAULT_NAMESPACE: str = "SFAPI"
    DEFAULT_CONFIG: SettingsDict = SettingsDict(
        host=config_settings.get("SCHOLAR_FLUX_REDIS_HOST") or "localhost",
        port=config_settings.get("SCHOLAR_FLUX_REDIS_PORT") or 6379,
        ttl=config_settings.get("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL"),
    )
    DEFAULT_RAISE_ON_ERROR: bool = False
    STORAGE_TYPE: str = "Redis"

    def __init__(
        self,
        host: str | None = None,
        namespace: str | None = None,
        ttl: int | None = None,
        raise_on_error: bool | None = None,
        verify_connection: bool = False,
        **redis_config: Any,
    ):
        """Initialize the Redis storage backend and connect to the Redis server.

        If no parameters are specified, the Redis storage will attempt to resolve the host and port using
        variables from the environment (loaded into scholar_flux.utils.config_settings at runtime).

        The resolved host and port are resolved from environment variables/defaults in the following order of priority:

            - SCHOLAR_FLUX_REDIS_HOST > REDIS_HOST > 'localhost'
            - SCHOLAR_FLUX_REDIS_PORT > REDIS_PORT > 6379

            When available:
            - SCHOLAR_FLUX_REDIS_USERNAME > cls.DEFAULT_CONFIG['username']
            - SCHOLAR_FLUX_REDIS_PASSWORD > cls.DEFAULT_CONFIG['password']

        Args:
            host (Optional[str]):
                Redis server host. Can be provided positionally or as a keyword argument. Defaults to
                'localhost' if not specified.
            namespace (Optional[str]):
                The prefix associated with each cache key. Defaults to DEFAULT_NAMESPACE if left `None`.
            ttl (Optional[int]):
                The total number of seconds that must elapse for a cached record to expire. While integers are the
                recommended input types, floats and strings that can reasonably be converted into integers will be.
                Also note: The value `-1` turns off TTL expiration when directly passed or resolved from config
                defaults. TTL is determined in the following order of priority:

                    - SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL (resolved from `config_settings.get()`)
                    - `RedisStorage.DEFAULT_CONFIG.get('ttl')` (if available)
                    - And `None` if neither of the above is set or defined.

            raise_on_error (Optional[bool]):
                Determines whether an error should be raised when encountering unexpected issues when interacting with
                Redis. If `None`, the `raise_on_error` attribute defaults to `RedisStorage.DEFAULT_RAISE_ON_ERROR`.
            verify_connection (bool):
                If True, verifies the Redis service is available immediately after initialization.
                Raises StorageCacheException if connection fails. Defaults to False.
            **redis_config:
                Configuration parameters required to connect to the Redis server. Typically includes parameters
                such as host, port, db, etc.

        Raises:
            RedisImportError: If redis module is not available or fails to load.

        """
        super().__init__()

        # optional dependencies set to None if not available
        if redis is None:
            raise RedisImportError

        if ttl is not None:
            redis_config["ttl"] = ttl  # -1 for infinite caching

        config: SettingsDict = self.get_default_config() | redis_config  # Overriding Redis defaults where available

        # TTL recorded in a separate variable and converts strings/floats into integers. Redis only accepts integer TTLs
        self.ttl = coerce_int(self._validate_ttl(config.pop("ttl")))  # Extracting TTL and Redis-specific settings
        self.config = config

        if host:
            self.config["host"] = host

        self.client = self.initialize_client(**SecretUtils.unmask_parameters(self.config))

        # Only override the defaults if available and the namespace/raise_on_error parameters are not directly provided
        self.namespace = self.DEFAULT_NAMESPACE if self.DEFAULT_NAMESPACE and not namespace else namespace
        self.raise_on_error = raise_on_error if raise_on_error is not None else self.DEFAULT_RAISE_ON_ERROR

        # catches all None and non-empty strings
        self._validate_prefix(self.namespace, required=True)

        self.lock = threading.Lock()
        if verify_connection:
            self.verify_connection()
        logger.info("RedisClient initialized and connected.")

    @classmethod
    def initialize_client(cls, *args: Any, **kwargs: Any) -> redis.Redis:
        """Convenience method for Initializing a new Redis client from positional and/or keyword arguments.

        Args:
            *args: positional arguments to pass to `RedisClient`
            **kwargs: keyword arguments to pass to `RedisClient`

        Returns:
            RedisClient: A new client when initialization is successful

        """
        if redis is None:
            raise RedisImportError()

        return redis.Redis(*args, **kwargs)

    @classmethod
    def get_default_config(cls) -> SettingsDict:
        """Get default configuration with current config_settings values.

        Reads from environment variables in order of priority:
        - SCHOLAR_FLUX_REDIS_HOST > cls.DEFAULT_CONFIG['host'] > REDIS_HOST > 'localhost'
        - SCHOLAR_FLUX_REDIS_PORT > DEFAULT_CONFIG['port'] > REDIS_PORT  > 6379

        When available:
        -  SCHOLAR_FLUX_REDIS_USERNAME > cls.DEFAULT_CONFIG['username']
        -  SCHOLAR_FLUX_REDIS_PASSWORD > cls.DEFAULT_CONFIG['password']

        Returns:
            SettingsDict: Configuration dictionary with a host, port, and masked authentication settings if available.

        """
        # Converts "None" to None when needed
        config_ttl = try_none(config_settings.get("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL"))

        config_username = try_none(config_settings.get("SCHOLAR_FLUX_REDIS_USERNAME")) or try_none(
            cls.DEFAULT_CONFIG.get("username")
        )
        config_password = try_none(config_settings.get("SCHOLAR_FLUX_REDIS_PASSWORD")) or try_none(
            cls.DEFAULT_CONFIG.get("password")
        )

        config = cls.DEFAULT_CONFIG | {
            "host": config_settings.get("SCHOLAR_FLUX_REDIS_HOST")
            or cls.DEFAULT_CONFIG.get("host")
            or config_settings.get("REDIS_HOST")
            or "localhost",
            "port": config_settings.get("SCHOLAR_FLUX_REDIS_PORT")
            or cls.DEFAULT_CONFIG.get("port")
            or config_settings.get("REDIS_PORT")
            or 6379,
            "ttl": config_ttl if config_ttl is not None else try_none(cls.DEFAULT_CONFIG.get("ttl")),
        }

        if config_username:
            config["username"] = SecretUtils.mask_secret(config_username, convert_object=False)

        if config_password:
            config["password"] = SecretUtils.mask_secret(config_password, convert_object=False)

        return config

    def clone(self) -> RedisStorage:
        """Helper method for creating a new RedisStorage with the same parameters.

        Note that the implementation of the RedisStorage is not able to be deep copied, and this method is provided for
        convenience in re-instantiation with the same configuration.

        """
        cls = self.__class__
        return cls(namespace=self.namespace, ttl=self.ttl, **self.config)

    def retrieve(self, key: str) -> Any | None:
        """Retrieve the value associated with the provided key from cache.

        Args:
            key (str): The key used to fetch the stored data from cache.

        Returns:
            Any:
                The value returned is deserialized JSON object if successful. Returns None if the key does not exist.

        """
        try:
            namespace_key = self._prefix(key)
            with self.lock:
                cache_data = cast("str | None", self.client.get(namespace_key))
            if cache_data is None:
                logger.info(f"Record for key {key} (namespace = '{self.namespace}') not found...")
                return None

            if isinstance(cache_data, bytes):
                cache_data = cache_data.decode()
            return JsonDataEncoder.deserialize(cache_data)

        except (RedisError, ConnectionError) as e:
            msg = f"Error during attempted retrieval of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheRetrievalException if self.raise_on_error else None, msg=msg
            )
        return None

    def retrieve_all(self) -> dict[str, Any]:
        """Retrieve all records from cache that match the current namespace prefix.

        Returns:
            dict[str, Any]:
                Dictionary of key-value pairs. Keys are original keys, values are JSON deserialized objects.

        Raises:
            RedisError: If there is an error during the retrieval of records under the namespace

        """
        try:
            matched_keys = self.retrieve_keys()
            results = {key: self.retrieve(key) for key in matched_keys}
            return results

        except (RedisError, ConnectionError) as e:
            msg = f"Error during attempted retrieval of records from namespace '{self.namespace}': {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheRetrievalException if self.raise_on_error else None, msg=msg
            )
        return {}

    def retrieve_keys(self) -> list[str]:
        """Retrieve all keys for records from cache that match the current namespace prefix.

        Returns:
            list[str]: A list of all keys saved under the current namespace.

        Raises:
            RedisError: If there is an error retrieving the record key

        """
        keys = []
        try:
            with self.lock:
                keys = [
                    key.decode() if isinstance(key, bytes) else key
                    for key in self.client.scan_iter(f"{self.namespace}:*")
                ]
        except (RedisError, ConnectionError) as e:
            msg = f"Error during attempted retrieval of all keys from namespace '{self.namespace}': {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheRetrievalException if self.raise_on_error else None, msg=msg
            )

        return keys

    def update(self, key: str, data: Any) -> None:
        """Update the cache by storing associated value with provided key.

        Args:
            key (str):
                The key used to store the serialized JSON string in cache.
            data (Any):
                A Python object that will be serialized into JSON format and stored. This includes standard data types
                like strings, numbers, lists, dictionaries, etc.

        Raises:
            RedisError: If an error occurs when attempting to insert or update a record

        """
        try:
            with self.lock:
                namespace_key = self._prefix(key)
                self.client.set(namespace_key, JsonDataEncoder.serialize(data))

                if self.ttl is not None:
                    self.client.expire(namespace_key, self.ttl)
                logger.debug(f"Cache updated for key: '{namespace_key}'")

        except (RedisError, ConnectionError) as e:
            msg = f"Error during attempted update of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheUpdateException if self.raise_on_error else None, msg=msg
            )

    def delete(self, key: str) -> bool | None:
        """Delete the value associated with the provided key from cache.

        This method indicates whether deletion was successful by returning True if the record was deleted and False
        if the record did not exist to be deleted.

        Args:
            key (str): The key used associated with the stored data from cache.

        Raises:
            RedisError: If there is an error deleting the record

        """
        try:
            namespace_key = self._prefix(key)
            with self.with_raise_on_error():
                cached = self.verify_cache(key)
            if cached:
                with self.lock:
                    self.client.delete(namespace_key)
                logger.debug(f"Key: {key}  (namespace = '{self.namespace}') successfully deleted")
                return True
            logger.info(f"Record for key {key} (namespace = '{self.namespace}') does not exist")
            return False

        except (RedisError, ConnectionError, StorageCacheException) as e:
            msg = f"Error during attempted deletion of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheDeletionException if self.raise_on_error else None, msg=msg
            )
        return None

    def delete_all(self) -> None:
        """Delete all records from cache that match the current namespace prefix.

        Raises:
            RedisError: If an error occurs when deleting records from the collection

        """
        # this function requires a namespace to avoid deleting unrelated data
        try:
            if not self.namespace:
                logger.warning(
                    "For safety purposes, the RedisStorage will not delete any records in the absence "
                    "of a namespace. Skipping..."
                )
                return

            with self.lock:
                matched_keys = list(self.client.scan_iter(f"{self.namespace}:*"))

                for key in matched_keys:
                    self.client.delete(key)

        except (RedisError, ConnectionError) as e:
            msg = f"Error during attempted deletion of all records from namespace '{self.namespace}': {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheDeletionException if self.raise_on_error else None, msg=msg
            )

    def verify_cache(self, key: str) -> bool:
        """Check if specific cache key exists.

        Args:
            key (str): The key to check its presence in the Redis storage backend.

        Returns:
            bool: True if the key is found otherwise False.

        Raises:
            ValueError: If provided key is empty or None.

            RedisError: If an error occurs when looking up a key

        """
        try:
            if not key or not isinstance(key, str):
                raise ValueError(f"Key invalid. Received {key} (namespace = '{self.namespace}')")
            namespace_key = self._prefix(key)

            with self.lock:
                if self.client.exists(namespace_key):
                    return True

        except (RedisError, ConnectionError, StorageCacheException) as e:
            msg = f"Error during the verification of the existence of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e,
                operation_exception_type=CacheVerificationException if self.raise_on_error else None,
                msg=msg,
            )

        return False

    def verify_connection(self) -> None:
        """Verifies that the RedisStorage is available for connection with the initialized configuration settings."""
        try:
            self.ping(self.client)
        except Exception as e:
            msg = f"Could not initialize a connection for the following storage device: {self.structure()}"
            self._handle_storage_exception(
                exception=e,
                operation_exception_type=StorageCacheException,
                msg=msg,
            )

    @classmethod
    def ping(cls, client: redis.Redis) -> None:
        """Attempts to ping the remote service."""
        client.ping()

    @classmethod
    def is_available(
        cls, host: str | None = None, port: int | None = None, verbose: bool = True, **kwargs: Any
    ) -> bool:
        """Helper class method for testing whether the Redis service is available and can be accessed.

        If Redis can be successfully reached, this function returns True, otherwise False.

        Args:
            host (Optional[str]): Indicates the location to attempt a connection. If None or an empty string, Defaults
                                  to localhost (the local computer) or the "host" entry from the class variable,
                                  DEFAULT_CONFIG.
            port (Optional[int]): Indicates the port where the service can be accessed If None or 0,
                                  Defaults to port 6379 or the "port" entry from the DEFAULT_CONFIG class
                                  variable.
            verbose (bool): Indicates whether to log at the levels, DEBUG and lower, or to log warnings only
            **kwargs: Optional keyword arguments for connection compatibility.

        Raises:
            TimeoutError: If a timeout error occurs when attempting to ping Redis
            ConnectionError: If a connection cannot be established

        """
        if redis is None:
            logger.warning("The redis module is not available")
            return False

        default_config = cls.get_default_config()
        redis_host = host or default_config["host"]
        redis_port = port or default_config["port"]

        kwargs.setdefault("socket_connect_timeout", 1)

        if username := default_config.get("username"):
            kwargs.setdefault("username", username)

        if password := default_config.get("password"):
            kwargs.setdefault("password", password)

        try:
            with cls.initialize_client(
                host=redis_host, port=redis_port, **SecretUtils.unmask_parameters(kwargs)
            ) as client:
                cls.ping(client)

            if verbose:
                logger.info(f"The Redis service is available at {redis_host}:{redis_port}")
            return True

        except (TimeoutError, ConnectionError) as e:
            logger.warning(f"An active Redis service could not be found at {redis_host}:{redis_port}: {e}")
            return False


__all__ = ["RedisStorage"]
