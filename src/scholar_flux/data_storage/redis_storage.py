import json

from scholar_flux.exceptions import RedisImportError
from scholar_flux.data_storage.base import BaseStorage
from typing import Any, Dict, List, Optional, cast, TYPE_CHECKING

from scholar_flux.utils.encoder import CacheDataEncoder
import  logging
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import redis
    from redis.exceptions import RedisError
else:
    try:
        import redis
        from redis.exceptions import RedisError
    except ImportError:
        redis = None
        RedisError = Exception

class RedisStorage(BaseStorage):

    DEFAULT_NAMESPACE: str = 'SFAPI'
    DEFAULT_REDIS_CONFIG = {'host':'localhost',
                      'port':6379,
                      'db':0}

    def __init__(self, redis_config: Optional[Dict[str, Any]] = None, namespace: Optional[str]=None, ttl: Optional[int] = None):
        """
        Initialize the Redis storage backend and connect to the Redis server.

        Args:
            redis_config Optional(Dict[str, Any]): Configuration parameters required to connect
                    to the Redis server. Typically includes parameters like host, port,
                    db, etc.
            namespace Optional[str]: The prefix associated with each cache key (DEFAULT = None)
            ttl Optional[int]: The total number of seconds that must elapse for a cache record
                    to expire (DEFAULT = None)
        Raises:
            RedisImportError: If redis module is not available or fails to load.
        """
        super().__init__()

        if not redis:
            raise RedisImportError

        self.client = redis.Redis(**redis_config or self.DEFAULT_REDIS_CONFIG)
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
            cache_data = cast(Optional[str], self.client.get(namespace_key))
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
            results = {key:self.retrieve(key) for key in matched_keys}
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
            keys = [key.decode() if isinstance(key,bytes) else key
                            for key in self.client.scan_iter(f"{self.namespace}:*")]
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

            matched_keys = [key for key in self.client.scan_iter(f"{self.namespace}:*")]

            for key in matched_keys:
                self.client.delete(key)

        except RedisError as e:
            logger.error(f"Error during attempted deletion of all keys from namespace '{self.namespace}: {e}'")

    def verify_cache(self,key: str) -> bool:
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
            logger.error(f"Error during the verification of the existence of key {key} (namespace = '{self.namespace}): {e}'")

        return False
