# /data_storage/redis_storage.py
"""
The scholar_flux.data_storage.redis_storage module implements the RedisStorage class that implements the abstract
methods required for compatibility with the DataCacheManager in the scholar_flux package.

This class implements caching by using the serialization-deserialization and caching features available in Redis
to store ProcessedResponse fields within the database for later CRUD operations.

WARNING: Ensure that the 'namespace' parameter is set to a non-empty, unique value for each logical cache.
Using an empty or shared namespace may result in accidental deletion or overwriting of unrelated data. For that reason,
the `delete_all` method does not perform any deletions unless a namespace exists
"""

from __future__ import annotations
from scholar_flux.exceptions import RedisImportError
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.utils.encoder import JsonDataEncoder
from typing import Any, Dict, List, Optional, cast, TYPE_CHECKING

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
    """
    Implements the storage methods necessary to interact with Redis with a similar interface as other storage methods.
    This implementation is designed to use a key-value store as a cache by which data can be stored and retrieved
    in a relatively straightforward manner similar to the In-Memory Storage.

    Examples:


        >>> from scholar_flux.data_storage import RedisStorage
        ### defaults to connecting to locally (localhost) on the default port for Redis (27017)
        >>> redis_storage = RedisStorage(namespace='testing_functionality')
        >>> print(redis_storage)
        # OUTPUT: RedisStorage(...)
        ### Adding records to the storage
        >>> redis_storage.update('record_page_1', {'id':52, 'article': 'A name to remember'})
        >>> redis_storage.update('record_page_2', {'id':55, 'article': 'A name can have many meanings'})
        ### Revising and overwriting a record
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
    DEFAULT_REDIS_CONFIG = {"host": "localhost", "port": 6379, "db": 0}

    def __init__(
        self,
        host: Optional[str] = None,
        namespace: Optional[str] = None,
        ttl: Optional[int] = None,
        **redis_config,
    ):
        """
        Initialize the Redis storage backend and connect to the Redis server.

        Args:
            host (Optional[str]): Redis server host. Can be provided positionally or as a keyword argument.
                                  Defaults to 'localhost' if not specified.
            namespace Optional[str]: The prefix associated with each cache key. Defaults to DEFAULT_NAMESPACE
                                     if left `None`.
            ttl Optional[int]: The total number of seconds that must elapse for a cache record
                    to expire. If not provided, ttl defaults to None.
            **redis_config Optional(Dict[Any, Any]): Configuration parameters required to connect
                    to the Redis server. Typically includes parameters like host, port,
                    db, etc.
        Raises:
            RedisImportError: If redis module is not available or fails to load.
        """
        super().__init__()

        if not redis:
            raise RedisImportError

        self.config: dict = self.DEFAULT_REDIS_CONFIG | redis_config

        if host:
            self.config["host"] = host

        self.client = redis.Redis(**self.config)

        # Only override the default if its available and the namespace is not directly provided
        self.namespace = self.DEFAULT_NAMESPACE if self.DEFAULT_NAMESPACE and not namespace else namespace

        # catches all None and non-empty strings
        self._validate_prefix(self.namespace, required=True)

        self.ttl = ttl
        self.lock = threading.Lock()
        logger.info("RedisClient initialized and connected.")

    def clone(self) -> RedisStorage:
        """
        Helper method for creating a new RedisStorage with the same parameters. Note that
        the implementation of the RedisStorage is not able to be deep copied, and this method
        is provided for convenience in reinstantiation with the same configuration.
        """
        cls = self.__class__
        return cls(namespace=self.namespace, ttl=self.ttl, **self.config)

    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve the value associated with the provided key from cache.

        Args:
            key (str): The key used to fetch the stored data from cache.

        Returns:
            Any: The value returned is deserialized JSON object if successful. Returns None
                if the key does not exist.
        """
        try:
            namespace_key = self._prefix(key)
            with self.lock:
                cache_data = cast("Optional[str]", self.client.get(namespace_key))
            if cache_data is None:
                logger.info(f"Record for key {key} (namespace = '{self.namespace}') not found...")
                return None

            if isinstance(cache_data, bytes):
                cache_data = cache_data.decode()
            return JsonDataEncoder.deserialize(cache_data)

        except RedisError as e:
            logger.error(f"Error during attempted retrieval of key {key} (namespace = '{self.namespace}'): {e}")
        return None

    def retrieve_all(self) -> Dict[str, Any]:
        """
        Retrieve all records from cache that match the current namespace prefix.

        Returns:
            dict: Dictionary of key-value pairs. Keys are original keys,
                values are JSON deserialized objects.
        Raises:
            RedisError: If there is an error during the retrieval of records under the namespace
        """
        try:
            matched_keys = self.retrieve_keys()
            results = {key: self.retrieve(key) for key in matched_keys}
            return results

        except RedisError as e:
            logger.error(f"Error during attempted retrieval of records from namespace '{self.namespace}': {e}")
        return {}

    def retrieve_keys(self) -> List[str]:
        """
        Retrieve all keys for records from cache that match the current namespace prefix.

        Returns:
            list: A list of all keys saved under the current namespace.

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
        except RedisError as e:
            logger.error(f"Error during attempted retrieval of all keys from namespace '{self.namespace}': {e}")

        return keys

    def update(self, key: str, data: Any) -> None:
        """
        Update the cache by storing associated value with provided key.

        Args:
            key (str): The key used to store the serialized JSON string in cache.
            data (Any): A Python object that will be serialized into JSON format and stored.
                This includes standard data types like strings, numbers, lists, dictionaries,
                etc.

        Raises:
            Redis: If an error occur when attempting to insert or update a record
        """
        try:
            with self.lock:
                namespace_key = self._prefix(key)
                self.client.set(namespace_key, JsonDataEncoder.serialize(data))

                if self.ttl is not None:
                    self.client.expire(namespace_key, self.ttl)
                logger.debug(f"Cache updated for key: {namespace_key}")

        except RedisError as e:
            logger.error(f"Error during attempted update of key {key} (namespace = '{self.namespace}': {e}")

    def delete(self, key: str) -> None:
        """
        Delete the value associated with the provided key from cache.

        Args:
            key (str): The key used associated with the stored data from cache.

        Raises:
            RedisError: If there is an error deleting the record
        """
        try:
            namespace_key = self._prefix(key)
            if self.verify_cache(key):
                with self.lock:
                    self.client.delete(namespace_key)
            else:
                logger.info(f"Record for key {key} (namespace = '{self.namespace}') does not exist")

        except RedisError as e:
            logger.error(f"Error during attempted deletion of key {key} (namespace = '{self.namespace}'): {e}")

    def delete_all(self) -> None:
        """
        Delete all records from cache that match the current namespace prefix.

        Raises:
            RedisError: If there an error occurred when deleting records from the collection
        """

        # this function requires a namespace to avoid deleting unrelated data
        try:
            if not self.namespace:
                logger.warning(
                    "For safety purposes, the RedisStorage will not delete any records in the absence "
                    "of a namespace. Skipping..."
                )
                return None

            with self.lock:
                matched_keys = list(self.client.scan_iter(f"{self.namespace}:*"))

                for key in matched_keys:
                    self.client.delete(key)

        except RedisError as e:
            logger.error(f"Error during attempted deletion of all keys from namespace '{self.namespace}': {e}")

    def verify_cache(self, key: str) -> bool:
        """
        Check if specific cache key exists.

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

        except RedisError as e:
            logger.error(
                f"Error during the verification of the existence of key {key} (namespace = '{self.namespace}'): {e}"
            )

        return False

    @classmethod
    def is_available(cls, host: str = "localhost", port: int = 6379, verbose: bool = True) -> bool:
        """
        Helper class method for testing whether the Redis service can be accessed.
        If so, this function returns True, otherwise False

        Args:
            host (str): Indicates the location to attempt a connection
            port (int): Indicates the port where the service can be accessed
            verbose (bool): Indicates whether to log at the levels, DEBUG and lower, or to log warnings only

        Raises:
            TimeoutError: If a timeout error occurs when attempting to ping Redis
            ConnectionError: If a connection cannot be established
        """
        if not redis:
            logger.warning("The redis module is not available")
            return False

        try:
            client = redis.Redis(host=host, port=port, socket_connect_timeout=1)
            client.ping()

            if verbose:
                logger.info(f"The Redis service is available at {host}:{port}")
            return True

        except (TimeoutError, ConnectionError) as e:
            logger.warning(f"An active Redis service could not be found at {host}:{port}: {e}")
            return False
