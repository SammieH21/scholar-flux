# /data_storage/sql_storage.py
"""The scholar_flux.data_storage.sql_storage module implements the SQLAlchemyStorage for the DataCacheManager.

This class implements  abstract methods required for compatibility with the DataCacheManager in the scholar_flux
package and uses SQLite as the default storage device. The `SQLAlchemyStorage` implements caching by recording each
of the fields of a ProcessedResponse into and parsed fields into a recursively encoded and serialized JSON data
structure. When retrieving the data, the data is then decoded and deserialized to return the original object.

Classes:
    - CacheTable:
        Defines the internal specification of the SQLAlchemy table that is used under the hood. This class inherits
        from Base/DeclarativeBase subclass to define its structure and function as a SQLAlchemy table
    - SQLCacheStorage:
        Inherits from the scholar_flux.data_storage.abc_storage subclass and Defines the mechanisms by which the
        storage uses SQLAlchemy to load, retrieve, and update, and delete data.

"""
from __future__ import annotations
import logging
from typing import Any, List, Dict, Optional, TYPE_CHECKING

from scholar_flux.utils.encoder import JsonDataEncoder
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.package_metadata import get_default_writable_directory
from scholar_flux.exceptions import (
    SQLAlchemyImportError,
    StorageCacheException,
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
)

import cattrs
import threading

logger = logging.getLogger(__name__)

# SQLAlchemy import logic for type checking and runtime
if TYPE_CHECKING:
    import sqlalchemy
    from sqlalchemy import create_engine, Column, String, Integer, JSON, exc
    from sqlalchemy.orm import DeclarativeBase, sessionmaker
else:
    try:
        import sqlalchemy  # imported for consistent implementation with redis/pymongo, etc.
        from sqlalchemy import create_engine, Column, String, Integer, JSON, exc
        from sqlalchemy.orm import DeclarativeBase, sessionmaker

    except ImportError:
        # Dummies for names so code still parses, but using stubs or Nones for runtime
        create_engine = None

        def Column(*args, **kwargs):
            """Placeholder function that returned when the sqlalchemy package is not available."""
            pass

        String = Integer = JSON = exc = None
        DeclarativeBase = object  # type: ignore
        sessionmaker = None
        sqlalchemy = None

# Define ORM classes if SQLAlchemy is available or for type checking
if TYPE_CHECKING or sqlalchemy is not None:

    class Base(DeclarativeBase):
        """Helper class from which future SQL tables can be defined from."""

        pass

    class CacheTable(Base):
        """Table that implements caching in a manner similar to a dictionary with key-cache data pairs."""

        __tablename__ = "cache"
        id = Column(Integer, primary_key=True, autoincrement=True)
        key = Column(String, unique=True, nullable=False)
        cache = Column(JSON, nullable=False)

else:
    # Runtime stubs so code can be parsed, but will error if actually used
    Base = None  # type: ignore
    CacheTable = None  # type: ignore


class SQLAlchemyStorage(ABCStorage):
    """Implements the storage methods necessary to interact with SQLite3 along with other SQL flavors via sqlalchemy.

    This implementation is designed to use a relational database as a cache by which data can be stored and
    retrieved in a relatively straightforward manner that associates records in key-value pairs similar to the In-Memory
    Storage.

    **Note**:

        This table uses the structure previously defined in the CacheTable to store records in a structured manner:

        ID:
            Automatically generated - identifies the unique record in the table
        Key:
            Is used to associate a specific cached record with a short human-readable (or hashed) string
        Cache:
            The JSON data associated with the record. To store the data, any nested, non-serializable data is first
            encoded before being unstructured and stored. On retrieving the data, the JSON string is decoded and
            restructured in order to return the original object.

    The SQLAlchemyStorage can be initialized as follows:

        ### Import the package and initialize the storage in a dedicated package directory :
        >>> from scholar_flux.data_storage import SQLAlchemyStorage
        # Defaults to connecting to creating a local, file-based sqlite cache within the default writable directory.
        # Verifies that the dependency for a basic sqlite service is actually available for use locally
        >>> assert SQLAlchemyStorage.is_available()
        >>> sql_storage = SQLAlchemyStorage(namespace='testing_functionality')
        >>> print(sql_storage)
        # OUTPUT: SQLAlchemyStorage(...)
        # Adding records to the storage
        >>> sql_storage.update('record_page_1', {'id':52, 'article': 'A name to remember'})
        >>> sql_storage.update('record_page_2', {'id':55, 'article': 'A name can have many meanings'})
        # Revising and overwriting a record
        >>> sql_storage.update('record_page_2', {'id':53, 'article': 'A name has many meanings'})
        >>> sql_storage.retrieve_keys() # retrieves all current keys stored in the cache under the namespace
        >>> sql_storage.retrieve_all()
        # OUTPUT: {'testing_functionality:record_page_1': {'id': 52,
        #           'article': 'A name to remember'},
        #          'testing_functionality:record_page_2': {'id': 53,
        #           'article': 'A name has many meanings'}}
        # OUTPUT: ['testing_functionality:record_page_1', 'testing_functionality:record_page_2']
        >>> sql_storage.retrieve('record_page_1') # retrieves the record for page 1
        # OUTPUT: {'id': 52, 'article': 'A name to remember'}
        >>> sql_storage.delete_all() # deletes all records from the namespace
        >>> sql_storage.retrieve_keys() # Will now be empty

    """

    DEFAULT_NAMESPACE: Optional[str] = None
    DEFAULT_CONFIG: Dict[str, Any] = {
        "url": lambda: "sqlite:///" + str(get_default_writable_directory("package_cache") / "data_store.sqlite"),
        "echo": False,
    }
    DEFAULT_RAISE_ON_ERROR: bool = False

    def __init__(
        self,
        url: Optional[str] = None,
        namespace: Optional[str] = None,
        ttl: None = None,
        raise_on_error: Optional[bool] = False,
        **sqlalchemy_config,
    ) -> None:
        """Initialize the SQLAlchemy storage backend and connect to the server indicated via the `url` parameter.

        This class uses the innate flexibility of SQLAlchemy to support backends such as SQLite, Postgres, DuckDB, etc.

        Args:
            url (Optional[str]):
                Database connection string. This can be provided positionally or as a keyword argument.
            namespace (Optional[str]):
                The prefix associated with each cache key. By default, this is None.
            ttl (None):
                Ignored. Included for interface compatibility; not implemented.
            raise_on_error (Optional[bool]):
                Determines whether an error should be raised when encountering unexpected issues when interacting with
                SQLAlchemy. If `None`, the `raise_on_error` attribute defaults to `SQLAlchemyStorage.DEFAULT_RAISE_ON_ERROR`.
            **sqlalchemy_config:
                Additional SQLAlchemy engine/session options passed to sqlalchemy.create_engine Typical parameters include
                the following:

                    - url (str): Indicates what server to connect to. Defaults to sqlite in the package directory.
                    - echo (bool): Indicates whether to show the executed SQL queries in the console.

        """
        # optional dependencies set to None if not available
        if sqlalchemy is None:
            raise SQLAlchemyImportError

        sqlalchemy_config["url"] = url or self.DEFAULT_CONFIG["url"]()
        sqlalchemy_config["echo"] = (
            sqlalchemy_config.get("echo")
            if isinstance(sqlalchemy_config.get("echo"), bool)
            else self.DEFAULT_CONFIG["echo"]
        )

        self.config: dict = sqlalchemy_config
        self.engine = create_engine(**self.config)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.converter = cattrs.Converter()
        self.namespace = namespace or self.DEFAULT_NAMESPACE
        self.raise_on_error = raise_on_error if raise_on_error is not None else self.DEFAULT_RAISE_ON_ERROR
        self.lock = threading.Lock()

        if ttl:
            logger.warning("TTL is not enabled for SQLAlchemyStorage. Skipping")
        self.ttl = None

        self._validate_prefix(self.namespace, required=False)

    def clone(self) -> SQLAlchemyStorage:
        """Helper method for creating a new SQLAlchemyStorage with the same parameters.

        Note that the implementation of the SQLAlchemyStorage is not able to be deep copied, and this method is provided
        for convenience in re-instantiation with the same configuration.

        """
        cls = self.__class__
        return cls(namespace=self.namespace, ttl=self.ttl, **self.config)

    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve the value associated with the provided key from cache.

        Args:
            key (str): The key used to fetch the stored data from cache.

        Returns:
            Any:
                The value returned is deserialized JSON object if successful. Returns None if the key does not exist.

        """
        with self.Session() as session, self.lock:
            try:
                namespace_key = self._prefix(key)
                record = session.query(CacheTable).filter(CacheTable.key == namespace_key).first()
                structured_data = self._deserialize_data(record.cache) if record else None
                if record:
                    return structured_data

            except exc.SQLAlchemyError as e:
                msg = f"Error during attempted retrieval of key {key} (namespace = '{self.namespace}'): {e}"
                self._handle_storage_exception(
                    exception=e,
                    operation_exception_type=CacheRetrievalException if self.raise_on_error else None,
                    msg=msg,
                )
            return None

    def retrieve_all(self) -> Dict[str, Any]:
        """Retrieve all records from cache.

        Returns:
            dict:
                Dictionary of key-value pairs. Keys are original keys, values are JSON deserialized objects.

        """
        with self.Session() as session, self.lock:
            cache = {}
            try:
                records = session.query(CacheTable).all()
                cache = {
                    str(record.key): self._deserialize_data(record.cache) if record else None
                    for record in records
                    if not self.namespace or str(record.key).startswith(self.namespace)
                }
            except exc.SQLAlchemyError as e:
                msg = f"Error during attempted retrieval of records from namespace '{self.namespace}': {e}"
                self._handle_storage_exception(
                    exception=e,
                    operation_exception_type=CacheRetrievalException if self.raise_on_error else None,
                    msg=msg,
                )
            return cache

    def retrieve_keys(self) -> List[str]:
        """Retrieve all keys for records from cache .

        Returns:
            list: A list of all keys saved via SQL.

        """
        with self.Session() as session, self.lock:
            try:
                keys = [
                    str(record.key)
                    for record in session.query(CacheTable).all()
                    if not self.namespace or str(record.key).startswith(self.namespace)
                ]
            except exc.SQLAlchemyError as e:
                msg = f"Error during attempted retrieval of all keys from namespace '{self.namespace}': {e}"
                self._handle_storage_exception(
                    exception=e,
                    operation_exception_type=CacheRetrievalException if self.raise_on_error else None,
                    msg=msg,
                )
                keys = []
            return keys

    def update(self, key: str, data: Any) -> None:
        """Update the cache by storing associated value with provided key.

        Args:
            key (str):
                The key used to store the serialized JSON string in cache.
            data (Any):
                A Python object that will be serialized into JSON format and stored. This includes standard data types
                like strings, numbers, lists, dictionaries, etc.

        """
        with self.Session() as session, self.lock:
            try:
                namespace_key = self._prefix(key)
                unstructured_data = self._serialize_data(data)
                record = session.query(CacheTable).filter(CacheTable.key == namespace_key).first()
                if record:
                    record.cache = unstructured_data
                else:
                    record = CacheTable(key=namespace_key, cache=unstructured_data)
                    session.add(record)
                    logger.debug(f"Cache updated for key: {namespace_key}")
                session.commit()

            except exc.SQLAlchemyError as e:
                session.rollback()
                msg = f"Error during attempted update of key {key} (namespace = '{self.namespace}': {e}"
                self._handle_storage_exception(
                    exception=e, operation_exception_type=CacheUpdateException if self.raise_on_error else None, msg=msg
                )

    def delete(self, key: str) -> None:
        """Delete the value associated with the provided key from cache.

        Args:
            key (str): The key used associated with the stored data from cache.

        """
        with self.Session() as session, self.lock:
            try:
                namespace_key = self._prefix(key)
                record = session.query(CacheTable).filter(CacheTable.key == namespace_key).first()
                if record:
                    session.delete(record)
                    session.commit()
                else:
                    logger.info(f"Record for key {key} (namespace = '{self.namespace}') does not exist")
            except exc.SQLAlchemyError as e:
                session.rollback()
                msg = f"Error during attempted deletion of key {key} (namespace = '{self.namespace}'): {e}"
                self._handle_storage_exception(
                    exception=e,
                    operation_exception_type=CacheDeletionException if self.raise_on_error else None,
                    msg=msg,
                )

    def delete_all(self) -> None:
        """Delete all records from cache that match the current namespace prefix."""
        with self.Session() as session, self.lock:
            try:
                if self.namespace:
                    num_deleted = session.query(CacheTable).filter(CacheTable.key.startswith(self.namespace)).delete()
                    session.commit()
                else:
                    num_deleted = session.query(CacheTable).delete()
                    session.commit()
                    logger.debug(f"Deleted {num_deleted} records.")
            except exc.SQLAlchemyError as e:
                msg = f"Error during attempted deletion of all records from namespace '{self.namespace}': {e}"
                session.rollback()
                self._handle_storage_exception(
                    exception=e,
                    operation_exception_type=CacheDeletionException if self.raise_on_error else None,
                    msg=msg,
                )

    def _serialize_data(self, record_data: Any) -> Any:
        """Helper method for serializing and encoding cached data.

        The data is first encoded, identifying nested structures that need to be encoded recursively.
        If a value is already in a serializable format, then the record is left as is. The data is finally
        unstructured and returned.

        Returns:
            The serialized version of the input data

        """
        encoded_record_data = JsonDataEncoder.encode(record_data)
        serialized_data = self.converter.unstructure(encoded_record_data)
        return serialized_data

    def _deserialize_data(self, record_data: Any) -> Any:
        """Handles the serialization and deserialization of the SQLCacheStorage.

        This implementation only attempts to structure the data in the case where it is a dictionary or list, as the
        CacheTable's cache column implements the JSON column schema. All other types are decoded and returned as is.

        """
        if not record_data:
            return record_data

        if isinstance(record_data, list):
            record_type: Optional[type] = list
        elif isinstance(record_data, dict):
            record_type = dict
        else:
            record_type = None

        structured_record_data = self.converter.structure(record_data, record_type) if record_type else record_data

        deserialized_data = JsonDataEncoder.decode(structured_record_data)
        return deserialized_data

    def verify_cache(self, key: str) -> bool:
        """Check if specific cache key exists.

        Args:
            key (str): The key to check its presence in the SQL storage backend.

        Returns:
            bool: True if the key is found otherwise False.

        Raises:
            ValueError: If provided key is empty or None.

        """
        if not key:
            raise ValueError(f"Key invalid. Received {key} (namespace = '{self.namespace}')")
        try:
            with self.with_raise_on_error():
                return self.retrieve(key) is not None
        except StorageCacheException as e:
            msg = f"Error during the verification of the existence of key {key} (namespace = '{self.namespace}'): {e}"
            self._handle_storage_exception(
                exception=e,
                operation_exception_type=CacheVerificationException if self.raise_on_error else None,
                msg=msg,
            )
        return False

    @classmethod
    def is_available(cls, url: Optional[str] = None, verbose: bool = True) -> bool:
        """Tests whether the SQL service can be accessed. If so, this function returns True, otherwise False.

        Args:
            url (str): Indicates the location to attempt a connection
            verbose (bool): Indicates whether to log at the levels, DEBUG and lower, or to log warnings only

        """
        if sqlalchemy is None:
            logger.warning("The sqlalchemy module is not available")
            return False

        db_url: str = url or cls.DEFAULT_CONFIG["url"]()
        try:
            engine = create_engine(url=db_url)
            with engine.connect():
                pass
            if verbose:
                logger.info(f"The SQL Service is available at {db_url}")
            return True

        except (exc.SQLAlchemyError, TimeoutError, ConnectionError) as e:
            logger.warning(f"An active SQL service could not be found at {db_url}: {e}")
            return False


__all__ = ["SQLAlchemyStorage"]
