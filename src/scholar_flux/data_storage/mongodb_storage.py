# /data_storage/mongo_storage.py
"""The scholar_flux.data_storage.mongodb_storage module implements the MongoDBStorage backend for the DataCacheManager.

This class implements the abstract methods required for compatibility with the scholar_flux.DataCacheManager to
ensure that each method can be injected as a dependency.

This class implements caching by using the prebuilt features available in MongoDB to store ProcessedResponse fields
within the database for later CRUD operations.

"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from scholar_flux.exceptions import (
    MongoDBImportError,
    StorageCacheException,
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
)

from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.utils import config_settings  # provides the loaded global environment configuration

import threading
import logging

logger = logging.getLogger(__name__)

from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:
    import pymongo
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError, ConnectionFailure
else:
    try:
        import pymongo
        from pymongo import MongoClient
        from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError, ConnectionFailure
    except ImportError:
        pymongo = None
        MongoClient = None
        ServerSelectionTimeoutError = Exception
        ConnectionFailure = Exception
        DuplicateKeyError = Exception
        PyMongoError = Exception


class MongoDBStorage(ABCStorage):
    """Implements the storage methods necessary to interact with MongoDB with a unified backend interface.

    The MongoDBStorage uses the same underlying interface as other scholar_flux storage classes for use with the
    DataCacheManager. This implementation is designed to use a key-value store as a cache by which data can be
    stored and retrieved in a relatively straightforward manner similar to the In-Memory Storage.

    Examples:
        >>> from scholar_flux.data_storage import MongoDBStorage
        # Defaults to connecting to locally (mongodb://127.0.0.1) on the default port for MongoDB (27017)
        # Verifies that a mongodb service is actually available locally on the default port
        >>> assert MongoDBStorage.is_available()
        >>> mongo_storage = MongoDBStorage(namespace='testing_functionality')
        >>> print(mongo_storage)
        # OUTPUT: MongoDBStorage(...)
        # Adding records to the storage
        >>> mongo_storage.update('record_page_1', {'id':52, 'article': 'A name to remember'})
        >>> mongo_storage.update('record_page_2', {'id':55, 'article': 'A name can have many meanings'})
        # Revising and overwriting a record
        >>> mongo_storage.update('record_page_2', {'id':53, 'article': 'A name has many meanings'})
        >>> mongo_storage.retrieve_keys() # retrieves all current keys stored in the cache under the namespace
        # OUTPUT: ['testing_functionality:record_page_1', 'testing_functionality:record_page_2']
        >>> mongo_storage.retrieve_all()
        # OUTPUT: {'testing_functionality:record_page_1': {'id': 52,
        #           'article': 'A name to remember'},
        #          'testing_functionality:record_page_2': {'id': 53,
        #           'article': 'A name has many meanings'}}
        >>> mongo_storage.retrieve('record_page_1') # retrieves the record for page 1
        # OUTPUT: {'id': 52, 'article': 'A name to remember'}
        >>> mongo_storage.delete_all() # deletes all records from the namespace
        >>> mongo_storage.retrieve_keys() # Will now be empty
        >>> mongo_storage.retrieve_all() # Will also be empty

    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        "host": config_settings.get("SCHOLAR_FLUX_MONGODB_HOST") or "mongodb://127.0.0.1",
        "port": config_settings.get("SCHOLAR_FLUX_MONGODB_PORT") or 27017,
        "db": "storage_manager_db",
        "collection": "result_page",
    }

    # for mongodb, the default
    DEFAULT_NAMESPACE: Optional[str] = None
    DEFAULT_RAISE_ON_ERROR: bool = False

    def __init__(
        self,
        host: Optional[str] = None,
        namespace: Optional[str] = None,
        ttl: Optional[float | int] = None,
        raise_on_error: Optional[bool] = None,
        **mongo_config,
    ):
        """Initialize the Mongo DB storage backend and connect to the Mongo DB server.

        If no parameters are specified, the MongoDB storage will default to the parameters derived from the
        scholar_flux.utils.config_settings.config dictionary, which, in turn, resolves the host and port from
        environment variables or the default MongoDB host/port in the following order of priority:

            - SCHOLAR_FLUX_MONGODB_HOST > MONGODB_HOST > 'mongodb://127.0.0.1' (localhost)
            - SCHOLAR_FLUX_MONGODB_PORT > MONGODB_PORT > 27017

        Args:
            host (Optional[str]):
                The host address where the Mongo Database can be found. The default is
                `'mongodb://127.0.0.1'`, which is the mongo server on the localhost.

                Each of the following are valid values for host:

                    - Simple hostname: 'localhost' (uses port parameter)
                    - Full URI: 'mongodb://localhost:27017' (ignores port parameter)
                    - Complex URI: 'mongodb://user:pass@host:27017/db?options'

            namespace (Optional[str]):
                The prefix associated with each cache key. By default, this is None.
            ttl (Optional[float | int]):
                The total number of seconds that must elapse for a cache record
            raise_on_error (Optional[bool]):
                Determines whether an error should be raised when encountering unexpected issues when interacting with
                MongoDB. If `None`, the `raise_on_error` attribute defaults to `MongoDBStorage.DEFAULT_RAISE_ON_ERROR`.

            **mongo_config (Dict[Any, Any]):
                Configuration parameters required to connect to the Mongo DB server.
                Typically includes parameters such as host, port, db, etc.

        Raises:
            MongoDBImportError: If db module is not available or fails to load.

        """
        # optional dependencies set to None if not available
        if pymongo is None:
            raise MongoDBImportError

        self.config = self.DEFAULT_CONFIG | mongo_config

        if host:
            self.config["host"] = host

        self.client: MongoClient = MongoClient(host=self.config["host"], port=self.config["port"])
        self.namespace = namespace if namespace is not None else self.DEFAULT_NAMESPACE
        self.raise_on_error = raise_on_error if raise_on_error is not None else self.DEFAULT_RAISE_ON_ERROR
        self.db = self.client[self.config["db"]]
        self.collection = self.db[self.config["collection"]]

        self.collection.create_index(
            [("expireAt", 1)],
            expireAfterSeconds=0,  # Use value in each document to determine whether or not to remove record
        )

        self._validate_prefix(namespace, required=False)

        self.ttl = ttl
        self.lock = threading.Lock()

    def clone(self) -> MongoDBStorage:
        """Helper method for creating a new MongoDBStorage with the same parameters.

        Note that the implementation of the MongoClient is not able to be deep copied. This method is provided for
        convenience for re-instantiation with the same configuration.

        """
        cls = self.__class__
        return cls(namespace=self.namespace, ttl=self.ttl, **self.config)

    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve the value associated with the provided key from cache.

        Args:
            key (str):
                The key used to fetch the stored data from cache.

        Returns:
            Any:
                The value returned is deserialized JSON object if successful. Returns None if the key does not exist.

        Raises:
            PyMongoError: If there is an error retrieving the record

        """
        try:
            namespace_key = self._prefix(key)
            with self.lock:
                cache_data = self.collection.find_one({"key": namespace_key})

            if cache_data:
                return {k: v for k, v in cache_data["data"].items() if k not in ("_id", "key")}

        except PyMongoError as e:
            msg = f"Error during attempted retrieval of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheRetrievalException if self.raise_on_error else None, msg=msg
            )

        logger.info(f"Record for key {key} (namespace = '{self.namespace}') not found...")
        return None

    def retrieve_all(self) -> Dict[str, Any]:
        """Retrieve all records from cache that match the current namespace prefix.

        Returns:
            dict: Dictionary of key-value pairs. Keys are original keys, values are JSON deserialized objects.

        Raises:
            PyMongoError: If there is an error during the retrieval of records under the namespace.

        """
        cache = {}
        try:
            with self.lock:
                cache_data = self.collection.find({}, {"key": 1, "data": 1, "_id": 0})
            if not cache_data:
                logger.info("Records not found...")
            else:
                cache = {
                    data["key"]: {k: v for k, v in data.items() if k not in ("_id", "key")}
                    for data in cache_data
                    if data.get("key") and (not self.namespace or data.get("key", "").startswith(self.namespace))
                }
        except PyMongoError as e:
            msg = f"Error during attempted retrieval of records from namespace '{self.namespace}': {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheRetrievalException if self.raise_on_error else None, msg=msg
            )

        return cache

    def retrieve_keys(self) -> List[str]:
        """Retrieve all keys for records from cache.

        Returns:
            list[str]: A list of all keys saved via MongoDB.

        Raises:
            PyMongoError: If there is an error retrieving the record key.

        """
        keys = []
        try:
            with self.lock:
                keys = self.collection.distinct("key")

            if self.namespace:
                keys = [key for key in keys if key.startswith(f"{self.namespace}:")]
        except PyMongoError as e:
            msg = f"Error during attempted retrieval of all keys from namespace '{self.namespace}': {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheRetrievalException if self.raise_on_error else None, msg=msg
            )
        return keys

    def update(self, key: str, data: Any):
        """Update the cache by storing associated value with provided key.

        Args:
            key (str):
                The key used to store the data in cache.
            data (Any):
                A Python object that will be serialized into JSON format and stored. This includes standard
                data types such as strings, numbers, lists, dictionaries, etc.

        Raises:
            PyMongoError: If an error occur when attempting to insert or update a record

        """
        try:
            namespace_key = self._prefix(key)
            data_dict = {"key": namespace_key, "data": data}
            if self.ttl is not None:
                data_dict["expireAt"] = datetime.now(timezone.utc) + timedelta(seconds=self.ttl)

            is_cached = self.verify_cache(namespace_key)
            with self.lock:
                if not is_cached:
                    self.collection.update_one({"key": namespace_key}, {"$set": data_dict}, upsert=True)
                else:
                    self.collection.replace_one({"key": namespace_key}, data_dict, upsert=True)
            logger.debug(f"Cache updated for key: {key} (namespace = '{self.namespace}')")

        except DuplicateKeyError as e:
            logger.warning(f"Duplicate key error updating cache: {e}")
        except (PyMongoError, StorageCacheException) as e:
            msg = f"Error during attempted update of key {key} (namespace = '{self.namespace}': {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheUpdateException if self.raise_on_error else None, msg=msg
            )

    def delete(self, key: str):
        """Delete the value associated with the provided key from cache.

        Args:
            key (str): The key used associated with the stored data from the cache.

        Raises:
            PyMongoError: If there is an error deleting the record

        """
        try:
            namespace_key = self._prefix(key)
            with self.lock:
                result = self.collection.delete_one({"key": namespace_key})
            if result.deleted_count > 0:
                logger.debug(f"Key: {key}  (namespace = '{self.namespace}') successfully deleted")
            else:
                logger.info(f"Record for key {key} (namespace = '{self.namespace}') does not exist")
        except PyMongoError as e:
            msg = f"Error during attempted deletion of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheDeletionException if self.raise_on_error else None, msg=msg
            )

    def delete_all(self):
        """Delete all records from cache that match the current namespace prefix.

        Raises:
            PyMongoError: If there an error occurred when deleting records from the collection

        """
        try:
            with self.lock:
                result = self.collection.delete_many({})
            if result.deleted_count > 0:
                logger.debug("Deleted all records.")
            else:
                logger.warning("No records present to delete")
        except PyMongoError as e:
            msg = f"Error during attempted deletion of all records from namespace '{self.namespace}': {e}"
            self._handle_storage_exception(
                exception=e, operation_exception_type=CacheDeletionException if self.raise_on_error else None, msg=msg
            )

    def verify_cache(self, key: str) -> bool:
        """Check if specific cache key exists.

        Args:
            key (str): The key to check its presence in the Mongo DB storage backend.

        Returns:
            bool: True if the key is found otherwise False.

        Raises:
            ValueError: If provided key is empty or None.
            CacheVerificationException: If an error occurs on data retrieval

        """
        if not key:
            raise ValueError(f"Key invalid. Received {key} (namespace = '{self.namespace}')")

        try:
            with self.with_raise_on_error():
                found_data = self.retrieve(key)
            return found_data is not None
        except (PyMongoError, StorageCacheException) as e:
            msg = f"Error during the verification of the existence of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e,
                operation_exception_type=CacheVerificationException if self.raise_on_error else None,
                msg=msg,
            )
        return False

    @classmethod
    def is_available(cls, host: Optional[str] = None, port: Optional[int] = None, verbose: bool = True) -> bool:
        """Helper method that indicates whether the MongoDB service is available or not.

        It attempts to establish a connection on the provided host and port and returns a boolean indicating if the
        connection was successful.

        Note that if the input to the `host` is a URI (e.g. mongodb://localhost:27017), any input provided to the
        `port` variable  will be ignored when `MongoClient` initializes the connection and use the URI exclusively.

        Args:
            host (Optional[str]): The IP of the host of the MongoDB service. If None or an empty string,
                                  Defaults to localhost (the local computer) or the "host" entry from the class variable,
                                  DEFAULT_CONFIG.
            port (Optional[int]): The port where the service is hosted. If None or 0, defaults to port, 27017  or the
                                  "port" entry from the DEFAULT_CONFIG class variable.
            verbose (bool): Indicates whether to log status messages. Defaults to True

        Returns:
            bool:
                Indicating whether or not the service was be successfully accessed. The value returned is True
                if successful and False otherwise.

        Raises:
            ServerSelectionTimeoutError: If a timeout error occurs when attempting to ping Mongo DB
            ConnectionFailure: If a connection cannot be established

        """
        if pymongo is None:
            logger.warning("The pymongo module is not available")
            return False

        mongodb_host = host or cls.DEFAULT_CONFIG["host"]
        mongodb_port = port or cls.DEFAULT_CONFIG["port"]

        try:
            client: MongoClient
            with MongoClient(host=mongodb_host, port=mongodb_port, serverSelectionTimeoutMS=1000) as client:
                client.server_info()

            if verbose:
                logger.info(f"The MongoDB service is available at {mongodb_host}:{mongodb_port}")
            return True

        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            logger.warning(f"An active MongoDB service could not be found at {mongodb_host}:{mongodb_port}: {e}")
            return False


__all__ = ["MongoDBStorage"]
