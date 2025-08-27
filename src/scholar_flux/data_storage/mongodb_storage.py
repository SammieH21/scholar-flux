from typing import Dict, Any, List, Optional, TYPE_CHECKING

from scholar_flux.exceptions import MongoDBImportError
from scholar_flux.data_storage.base import ABCStorage

import logging
logger = logging.getLogger(__name__)

from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:
    import pymongo
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError, PyMongoError
else:
    try:
        import pymongo
        from pymongo import MongoClient
        from pymongo.errors import DuplicateKeyError, PyMongoError
    except ImportError:
        pymongo = None
        MongoClient = None
        DuplicateKeyError = Exception
        PyMongoError = Exception

class MongoDBStorage(ABCStorage):
    """
    Storage for managing cache with mongodb backend.

    This class provides methods to check the cache, delete from the cache,
        update it with new data and retrieve data from the cache.
    """


    DEFAULT_CONFIG: Dict[str, Any] = {
        'host': 'mongodb://127.0.0.1',
        'port': 27017,
        'db': 'storage_manager_db',
        'collection': 'result_page'
    }

    # for mongodb, the default
    DEFAULT_NAMESPACE: Optional[str] = None

    def __init__(self,
                 host: Optional[str] = None,
                 namespace: Optional[str]=None,
                 ttl: Optional[int] = None,
                 **mongo_config):
        """
        Initialize the Mongo DB storage backend and connect to the Mongo DB server.

        Args:
            host (Optional[str]): The host address where the Mongo Database can be found.
                                  The default is `'mongodb://127.0.0.1'`, which is the mongo server on the localhost
            namespace (Optional[str]): The prefix associated with each cache key. By default, this is None.
            ttl (Optional[int]): The total number of seconds that must elapse for a cache record
            **mongo_config (Dict[Any, Any]): Configuration parameters required to connect
                to the Mongo DB server. Typically includes parameters like host, port,
                db, etc.

        Raises:
            MongoDBImportError: If db module is not available or fails to load.
        """

        if not pymongo:
            raise MongoDBImportError

        self.config = self.DEFAULT_CONFIG | mongo_config

        if host:
            self.config['host'] = host

        self.client: MongoClient = MongoClient(host=self.config['host'], port=self.config['port'])
        self.namespace = namespace if namespace is not None else self.DEFAULT_NAMESPACE
        self.db = self.client[self.config['db']]
        self.collection = self.db[self.config['collection']]

        self.collection.create_index(
            [("expireAt", 1)],
            expireAfterSeconds=0  # Use value in each document to determine whether or not to remove record
        )

        self.ttl = ttl


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
            cache_data = self.collection.find_one({'key': namespace_key})

            if cache_data:
                return {k:v for k, v in cache_data['data'].items() if k not in ('_id','key')}

        except PyMongoError as e:
            logger.error(f"Error retrieving all records: {e}")

        logger.info(f"Record for key {key} (namespace = '{self.namespace}') not found...")
        return None


    def retrieve_all(self) -> Dict[str, Any]:
        """
        Retrieve all records from cache that match the current namespace prefix.

        Returns:
            dict: Dictionary of key-value pairs. Keys are original keys,
                values are JSON deserialized objects.
        """
        cache = {}
        try:
            cache_data = self.collection.find({},{"key": 1, "data": 1, "_id": 0})
            if not cache_data:
                logger.info("Records not found...")
            else:
                cache = {data['key']:{k:v for k,v in data.items()
                                      if k not in ('_id','cache_key')}
                        for data in cache_data
                        if data.get('key') and (not self.namespace or
                         data.get('key','').startswith(self.namespace))}
        except PyMongoError as e:
            logger.error(f"Error retrieving all records: {e}")
        return cache


    def retrieve_keys(self) -> List[str]:
            keys = []
            try:
                keys = self.collection.distinct('key')

                if self.namespace:
                    keys = [key for key in keys if key.startswith(f"{self.namespace}:")]
            except PyMongoError as e:
                logger.error(f"Error retrieving keys: {e}")
            return keys

    def update(self, key: str, data: Any):
        """
        Update the cache by storing associated value with provided key.

        Args:
            key (str): The key used to store the data in cache.
            data (Any): A Python object that will be serialized into JSON format and stored.
                This includes standard data types like strings, numbers, lists, dictionaries,
                etc.
        """
        try:
            namespace_key = self._prefix(key)
            data_dict = {'data':data}
            if self.ttl is not None:
                data_dict['expireAt'] = datetime.now(timezone.utc) + timedelta(seconds=self.ttl)
            if not self.verify_cache(namespace_key):
                self.collection.update_one(
                    {'key': namespace_key},
                    {"$set": data_dict},
                    upsert=True
                )
            else:
                self.collection.replace_one(
                    {'key': namespace_key},
                    data_dict,
                    upsert=True
                )
            logger.debug(f"Cache updated for key: {key} (namespace = '{self.namespace}')")

        except DuplicateKeyError as e:
           logger.warning(f"Duplicate key error updating cache: {e}")
        except PyMongoError as e:
            logger.error(f"Error updating key {key}: {e}")

    def delete(self, key: str):
        try:
            namespace_key = self._prefix(key)
            result = self.collection.delete_one({'key': namespace_key})
            if result.deleted_count > 0:
                logger.debug(f"Key: {key}  (namespace = '{self.namespace}') successfully deleted")
            else:
               logger.info(f"Key: {key}  (namespace = '{self.namespace}') does not exist in cache.")
        except PyMongoError as e:
            logger.error(f"Error deleting key {key}: {e}")

    def delete_all(self):
        try:
            result = self.collection.delete_many({})
            if result.deleted_count > 0:
                 logger.debug("Deleted all records.")
            else:
                 logger.warning("No records present to delete")
        except PyMongoError as e:
            logger.error(f"Error deleting all records: {e}")

    def verify_cache(self, key: str) -> bool:
        """
        Check if specific cache key exists.

        Args:
            key (str): The key to check its presence in the Mongo DB storage backend.

        Returns:
            bool: True if the key is found otherwise False.
        Raises:
            ValueError: If provided key is empty or None.
        """
        if not key:
            raise ValueError(f"Key invalid. Received {key} (namespace = '{self.namespace}')")

        found_data = self.retrieve(key)
        return found_data is not None
