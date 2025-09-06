import json

from scholar_flux.exceptions import RedisImportError
from scholar_flux.data_storage.abc_storage import ABCStorage
from typing import Any, Dict, List, Optional, cast, TYPE_CHECKING

from scholar_flux.utils.encoder import CacheDataEncoder
import logging

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
            namespace Optional[str]: The prefix associated with each cache key. Defaults to `None`.
            ttl Optional[int]: The total number of seconds that must elapse for a cache record
                    to expire (DEFAULT = None)
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
        self.namespace = namespace if namespace is not None else self.DEFAULT_NAMESPACE
        if not self.namespace:
            raise KeyError("A namespace must be provided for the Redis Cache")

        self.ttl = ttl
        logger.info("RedisClient initialized and connected.")

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
            cache_data = cast("Optional[str]", self.client.get(namespace_key))
            if cache_data is None:
                logger.info(f"Record for key {key} (namespace = '{self.namespace}') not found...")
                return None

            if isinstance(cache_data, bytes):
                cache_data = cache_data.decode()
            return CacheDataEncoder.decode(json.loads(cache_data))

        except RedisError as e:
            logger.error(f"Error during attempted retrieval of key {key} (namespace = '{self.namespace}): {e}'")
        return None

    def retrieve_all(self) -> Dict[str, Any]:
        """
        Retrieve all records from cache that match the current namespace prefix.

        Returns:
            dict: Dictionary of key-value pairs. Keys are original keys,
                values are JSON deserialized objects.
        """
        try:
            matched_keys = self.retrieve_keys()
            results = {key: self.retrieve(key) for key in matched_keys}
            return results

        except RedisError as e:
            logger.error(f"Error during attempted retrieval of all keys from namespace '{self.namespace}: {e}'")
        return {}

    def retrieve_keys(self) -> List[str]:
        """
        Retrieve all keys for records from cache that match the current namespace prefix.

        Returns:
            list: A list of all keys saved under the current namespace.
        """
        keys = []
        try:
            keys = [
                key.decode() if isinstance(key, bytes) else key for key in self.client.scan_iter(f"{self.namespace}:*")
            ]
        except RedisError as e:
            logger.error(f"Error during attempted retrieval of all keys from namespace '{self.namespace}: {e}'")

        return keys

    def update(self, key: str, data: Any) -> None:
        """
        Update the cache by storing associated value with provided key.

        Args:
            key (str): The key used to store the serialized JSON string in cache.
            data (Any): A Python object that will be serialized into JSON format and stored.
                This includes standard data types like strings, numbers, lists, dictionaries,
                etc.
        """
        try:
            namespace_key = self._prefix(key)
            self.client.set(namespace_key, json.dumps(CacheDataEncoder.encode(data)))
            if self.ttl is not None:
                self.client.expire(namespace_key, self.ttl)
            logger.debug(f"Cache updated for key: {namespace_key}")

        except RedisError as e:
            logger.error(f"Error during attempted update of key {key} (namespace = '{self.namespace}: {e}'")

    def delete(self, key: str) -> None:
        """
        Delete the value associated with the provided key from cache.

        Args:
            key (str): The key used associated with the stored data from cache.

        """
        try:
            namespace_key = self._prefix(key)
            if self.verify_cache(key):
                self.client.delete(namespace_key)
            else:
                logger.info(f"Record for key {key} (namespace = '{self.namespace}') does not exist")

        except RedisError as e:
            logger.error(f"Error during attempted deletion of key {key} (namespace = '{self.namespace}): {e}'")

    def delete_all(self) -> None:
        """
        Delete all records from cache that match the current namespace prefix.
        """

        # this function requires a namespace for safety purposes in
        # not deleting unrelated data
        try:
            if not self.namespace:
                return None

            # matched_keys = [key for key in self.client.scan_iter(f"{self.namespace}:*")]
            matched_keys = list(self.client.scan_iter(f"{self.namespace}:*"))

            for key in matched_keys:
                self.client.delete(key)

        except RedisError as e:
            logger.error(f"Error during attempted deletion of all keys from namespace '{self.namespace}: {e}'")

    def verify_cache(self, key: str) -> bool:
        """
        Check if specific cache key exists.

        Args:
            key (str): The key to check its presence in the Redis storage backend.

        Returns:
            bool: True if the key is found otherwise False.
        Raises:
            ValueError: If provided key is empty or None.
        """
        try:
            if not key:
                raise ValueError(f"Key invalid. Received {key} (namespace = '{self.namespace}')")
            namespace_key = self._prefix(key)

            if self.client.exists(namespace_key):
                return True

        except RedisError as e:
            logger.error(
                f"Error during the verification of the existence of key {key} (namespace = '{self.namespace}): {e}'"
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
