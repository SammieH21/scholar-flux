# /data_storage/sql_storage.py
"""The scholar_flux.data_storage.sql_storage module implements SQLAlchemy-based storage devices for response caching.

This module implements the SQLAlchemyStorage class and DuckDBStorage subclass, both of which implement the abstract
methods required for compatibility with the scholar_flux.DataCacheManager. This module provides SQL database storage
using the SQLAlchemy Object-Relational Mapper (ORM), using SQLite as the default backend.

When `ProcessedResponse` fields are cached, this implementation uses the `JsonDataEncoder` to recursively encode and
serialize each field within a storage compatible JSON data structure. When retrieving data, it is decoded and
deserialized to return the original object.

Classes:
    - CacheTable:
        Defines the internal specification of the SQLAlchemy table used for caching. Inherits from
        Base/DeclarativeBase to define its structure as a SQLAlchemy ORM model.
    - SQLAlchemyStorage:
        Primary storage class that uses SQLAlchemy to perform CRUD operations. Supports SQLite,
        PostgreSQL, MySQL, and other SQLAlchemy-compatible databases.
    - DuckDBStorage:
        Extends SQLAlchemyStorage with DuckDB-specific configuration and validation. Requires the
        `duckdb_engine` package for SQLAlchemy dialect support.

"""

from __future__ import annotations
import logging
from typing import Any, Optional, TYPE_CHECKING

from scholar_flux.utils.encoder import JsonDataEncoder
from scholar_flux.utils.helpers import coerce_str, try_none
from scholar_flux.utils import config_settings  # global environment configuration
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.package_metadata import get_default_writable_directory
from scholar_flux.security.utils import SecretUtils
from scholar_flux.utils.settings_utils import SettingsDict, SettingsDictType
from scholar_flux.exceptions import (
    SQLAlchemyImportError,
    DuckDBImportError,
    StorageCacheException,
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
    CacheParameterValidationException,
)
from urllib.parse import urlparse

import cattrs
import threading
import importlib.util
import re

logger = logging.getLogger(__name__)

# SQLAlchemy import logic for type checking and runtime
if TYPE_CHECKING:
    import sqlalchemy
    from sqlalchemy import create_engine, Engine, Column, String, Integer, Sequence, JSON, exc
    from sqlalchemy.orm import DeclarativeBase, sessionmaker
else:
    try:
        import sqlalchemy  # imported for consistent implementation with redis/pymongo, etc.
        from sqlalchemy import create_engine, Engine, Column, String, Integer, Sequence, JSON, exc
        from sqlalchemy.orm import DeclarativeBase, sessionmaker

    except ImportError:
        # Dummies for names so code still parses, but using stubs or Nones for runtime
        create_engine = None

        def Column(*args, **kwargs):
            """Placeholder function that is returned when the sqlalchemy package is not available."""
            pass

        String = Integer = Sequence = JSON = exc = Engine = None
        DeclarativeBase = object
        sessionmaker = None
        sqlalchemy = None

# Define ORM classes if SQLAlchemy is available or for type checking
if TYPE_CHECKING or sqlalchemy is not None:

    class Base(DeclarativeBase):
        """Helper class that future SQLAlchemy-compatible tables inherit from."""

        pass

    class CacheTable(Base):
        """Table that implements caching in a manner similar to a dictionary with key-cache data pairs."""

        __tablename__ = "cache"
        id = Column(Integer, Sequence("cache_id_sequence"), primary_key=True)
        key = Column(String, unique=True, nullable=False)
        cache = Column(JSON, nullable=False)

else:
    # Runtime stubs so code can be parsed, but will error if actually used
    Base = None
    CacheTable = None

URI_SCHEMA_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9+]+:///?")


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
    DEFAULT_CONFIG: SettingsDictType = SettingsDict(
        url=lambda: SQLAlchemyStorage.get_default_url(),
        echo=False,
    )
    DEFAULT_RAISE_ON_ERROR: bool = False
    STORAGE_TYPE: str = "SQL"

    def __init__(
        self,
        url: Optional[str] = None,
        namespace: Optional[str] = None,
        ttl: None = None,
        raise_on_error: Optional[bool] = False,
        verify_connection: bool = False,
        **sqlalchemy_config: Any,
    ) -> None:
        """Initialize the SQLAlchemy storage backend and connect to the server indicated via the `url` parameter.

        This class uses the innate flexibility of SQLAlchemy to support backends such as SQLite, Postgres, DuckDB, etc.

        Args:
            url (Optional[str]):
                Database connection string. This can be provided positionally or as a keyword argument.
            namespace (Optional[str]):
                The prefix associated with each cache key. By default, this is None.
            ttl (None):
                Ignored. Included for interface compatibility, but not implemented.
            raise_on_error (Optional[bool]):
                Determines whether an error should be raised when encountering unexpected issues when interacting with
                SQLAlchemy. If `None`, the `raise_on_error` attribute defaults to `SQLAlchemyStorage.DEFAULT_RAISE_ON_ERROR`.
            verify_connection (bool):
                If True, verifies the SQL service is available immediately after initialization.
                Raises StorageCacheException if connection fails. Defaults to False.
            **sqlalchemy_config:
                Additional SQLAlchemy engine/session options passed to `sqlalchemy.create_engine`. Typical parameters include
                the following:

                    - url (str): Indicates what server to connect to. Defaults to sqlite in the package directory.
                    - echo (bool): Indicates whether to show the executed SQL queries in the console.

        """
        # optional dependencies set to None if not available
        if sqlalchemy is None:
            raise SQLAlchemyImportError

        default_config = self.get_default_config()
        sqlalchemy_config["url"] = url or default_config["url"]()  # lazy writable path creation for defaults
        sqlalchemy_config["echo"] = (
            sqlalchemy_config.get("echo") if isinstance(sqlalchemy_config.get("echo"), bool) else default_config["echo"]
        )

        self.config: SettingsDictType = SettingsDict(sqlalchemy_config)
        self.engine = create_engine(**self.config)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.converter = cattrs.Converter()
        self.namespace = namespace or self.DEFAULT_NAMESPACE
        self.raise_on_error = raise_on_error if raise_on_error is not None else self.DEFAULT_RAISE_ON_ERROR
        if verify_connection:
            self.verify_connection()
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

    def retrieve_all(self) -> dict[str, Any]:
        """Retrieve all records from cache.

        Returns:
            dict[str, Any]:
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

    def retrieve_keys(self) -> list[str]:
        """Retrieve all keys for records from cache.

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
                msg = f"Error during attempted update of key {key} (namespace = '{self.namespace}'): {e}"
                self._handle_storage_exception(
                    exception=e, operation_exception_type=CacheUpdateException if self.raise_on_error else None, msg=msg
                )

    def delete(self, key: str) -> Optional[bool]:
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
                    logger.debug(f"Key: {key}  (namespace = '{self.namespace}') successfully deleted")
                    return True

                logger.info(f"Record for key {key} (namespace = '{self.namespace}') does not exist")
                return False
            except exc.SQLAlchemyError as e:
                session.rollback()
                msg = f"Error during attempted deletion of key {key} (namespace = '{self.namespace}'): {e}"
                self._handle_storage_exception(
                    exception=e,
                    operation_exception_type=CacheDeletionException if self.raise_on_error else None,
                    msg=msg,
                )
            return None

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
        """Handles the deserialization of cached data for the SQLAlchemyStorage.

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

    def verify_connection(self) -> None:
        """Verifies that the SQLAlchemyStorage is available for connection with initialized configuration settings."""
        try:
            self.ping(self.engine)
        except Exception as e:
            msg = f"Could not initialize a connection for the following storage device: {self.structure()}"
            self._handle_storage_exception(
                exception=e,
                operation_exception_type=StorageCacheException,
                msg=msg,
            )

    @classmethod
    def verify_url_string(cls, url: str) -> None:
        """Helper method for verifying that the current URI has a valid SQLAlchemy resource identifier."""
        if not isinstance(url, str):
            raise CacheParameterValidationException(f"Expected a valid SQLAlchemy URI, but received type {type(url)}")

        url_case = url.lower()
        if (
            URI_SCHEMA_PATTERN.search(url_case) is None
            or (url_case.startswith("duckdb:") and not url_case.startswith("duckdb:///"))
            or (url_case.startswith("sqlite:") and not url_case.startswith("sqlite:///"))
        ):
            raise CacheParameterValidationException(
                "Only URIs with valid SQL protocols are supported (e.g., postgres://, sqlite:///, duckdb:///, etc.). "
                f"Received: '{url}'"
            )

        result = urlparse(url)

        # If the path is non-empty, then remove special characters after the scheme
        if path := coerce_str(result.path):
            path = path.strip(":/ ")
        if not path:
            raise CacheParameterValidationException(
                f"Expected a path after the protocol in the SQLAlchemy URI. Only the scheme was received: {url}"
            )

    @classmethod
    def create_default_url(cls) -> str:
        """Creates a default URL within the writable directory for the current SQLAlchemyStorage class or subclass."""
        default_dir = config_settings.get("SCHOLAR_FLUX_CACHE_DIRECTORY")
        url_path = get_default_writable_directory("package_cache", default=default_dir) / "data_store.sqlite"
        return f"sqlite:///{url_path}"

    @classmethod
    def get_default_url(cls) -> str:
        """Retrieves the SQLAlchemy URL from the environment configuration, falling back to the default when invalid.

        Returns:
            str:
                The validated URL from the environment configuration if valid. Otherwise the default URL generated via
                `cls.create_default_url()`.

        Note: This method first attempts to validate the URL string from the environment variable,
        `SCHOLAR_FLUX_SQLALCHEMY_URL`, using the `cls.verify_url_string` class method. When validation fails, the
        default for the current class is returned via `cls.create_default_url` instead.

        """
        config_url = try_none(SecretUtils.unmask_secret(config_settings.get("SCHOLAR_FLUX_SQLALCHEMY_URL")))
        if config_url:
            try:
                cls.verify_url_string(config_url)
                return config_url
            except CacheParameterValidationException:
                storage = "SQLAlchemy" if cls.STORAGE_TYPE == "SQL" else cls.STORAGE_TYPE
                logger.info(
                    f"The environment variable, SCHOLAR_FLUX_SQLALCHEMY_URL, is not a valid {storage} URL. "
                    f"Returning the default..."
                )

        return cls.create_default_url()

    @classmethod
    def get_default_config(cls) -> SettingsDictType:
        """Get default configuration with current config_settings values.

        Returns:
            SettingsDict: A dictionary configuration with the default URL and `echo` (for debugging SQL statements).

        """
        default_url = cls.DEFAULT_CONFIG.get("url")
        url_func = default_url if callable(default_url) else lambda: default_url

        return cls.DEFAULT_CONFIG | {"url": url_func, "echo": cls.DEFAULT_CONFIG.get("echo") or False}

    @classmethod
    def ping(cls, engine: Engine) -> None:
        """Verifies that the client can successfully connect to the database."""
        with engine.connect():
            pass

    @classmethod
    def is_available(cls, url: Optional[str] = None, verbose: bool = True, **kwargs: Any) -> bool:
        """Tests whether the SQL service can be accessed. If so, this function returns True, otherwise False.

        Args:
            url (str): Indicates the location to attempt a connection
            verbose (bool): Indicates whether to log at the levels, DEBUG and lower, or to log warnings only
            **kwargs: No-Op keyword arguments for compatibility with config connection availability checks

        """
        if sqlalchemy is None:
            logger.warning("The sqlalchemy module is not available")
            return False

        db_url: str = url or cls.get_default_config()["url"]()
        try:
            engine = create_engine(url=db_url)
            cls.ping(engine)

            if verbose:
                logger.info(f"The {cls.STORAGE_TYPE} Service is available at {db_url}")
            return True

        except (exc.SQLAlchemyError, TimeoutError, ConnectionError) as e:
            logger.warning(f"An active {cls.STORAGE_TYPE} service could not be found at {db_url}: {e}")
            return False


class DuckDBStorage(SQLAlchemyStorage):
    """This class extends the `SQLAlchemyStorage` device to support DuckDB as a supported storage device.

    Note that this class requires the `duckdb_engine` and `sqlalchemy` packages and will raise an error without both
    being installed. This class can be initialized in the same manner as SQLAlchemy, only requiring that the passed
    url has a valid `duckdb:///` URI scheme.

    """

    DEFAULT_CONFIG: SettingsDictType = SettingsDict(
        {
            "url": lambda: DuckDBStorage.get_default_url(),
            "echo": False,
        }
    )
    STORAGE_TYPE: str = "DuckDB"

    def __init__(
        self,
        url: Optional[str] = None,
        namespace: Optional[str] = None,
        ttl: None = None,
        raise_on_error: Optional[bool] = False,
        verify_connection: bool = False,
        **sqlalchemy_config: Any,
    ) -> None:
        """Initialize the DuckDBStorage storage backend and connect to the server indicated via the `url` parameter.

        This class extends the original SQLAlchemyStorage to provide basic helpers that aid in the creation of both
        simple and complex sessions using the DuckDB engine.

        Args:
            url (Optional[str]):
                Database connection string. All URLs must begin with `duckdb:///`. A CacheParameterValidationException
                will be raised if the URL is invalid or does not contain the required scheme.
            namespace (Optional[str]):
                The prefix associated with each cache key. By default, this is None.
            ttl (None):
                Ignored. Included for interface compatibility; not implemented.
            raise_on_error (Optional[bool]):
                Determines whether an error should be raised when encountering unexpected issues when interacting with
                SQLAlchemy. If `None`, the `raise_on_error` attribute defaults to `SQLAlchemyStorage.DEFAULT_RAISE_ON_ERROR`.
            verify_connection (bool):
                If True, verifies the SQL service is available immediately after initialization.
                Raises StorageCacheException if connection fails. Defaults to False.
            **sqlalchemy_config:
                Additional SQLAlchemy engine/session options passed to `sqlalchemy.create_engine`. Typical parameters
                include the following:

                - url (str): Indicates what server to connect to. Defaults to sqlite in the package directory.
                - echo (bool): Indicates whether to show the executed SQL queries in the console.

        """
        duckdb_url = url or self.DEFAULT_CONFIG["url"]()
        self.verify_url_string(duckdb_url)

        if not importlib.util.find_spec("duckdb_engine"):
            raise DuckDBImportError()

        super().__init__(duckdb_url, namespace, ttl, raise_on_error, verify_connection, **sqlalchemy_config)

    @classmethod
    def verify_url_string(cls, url: str) -> None:
        """Helper method for verifying that the current URI is a valid DuckDB resource identifier."""
        if not isinstance(url, str):
            raise CacheParameterValidationException(f"Expected a valid DuckDB URI, but received type {type(url)}")
        result = urlparse(url)
        if not url.lower().startswith("duckdb:///"):
            raise CacheParameterValidationException(
                f"Only URIs with `duckdb:///' protocols are supported. Received: '{url}'"
            )

        # If the path is non-empty, then remove special characters after the scheme
        if path := coerce_str(result.path):
            path = path.strip(":/ ")
        if not path:
            raise CacheParameterValidationException(
                f"Expected a path after the duckdb:/// protocol in the URI. Only the scheme was received: {url}"
            )

    @classmethod
    def create_default_url(cls) -> str:
        """Creates a valid DuckDB URL within the default writable package cache directory."""
        default_dir = config_settings.get("SCHOLAR_FLUX_CACHE_DIRECTORY")
        url_path = get_default_writable_directory("package_cache", default=default_dir) / "data_store.duckdb"
        return f"duckdb:///{url_path}"

    @classmethod
    def is_available(cls, url: Optional[str] = None, verbose: bool = True, **kwargs: Any) -> bool:
        """Tests whether the SQL service can be accessed. If so, this function returns True, otherwise False.

        Args:
            url (str): Indicates the location to attempt a connection
            verbose (bool): Indicates whether to log at the levels, DEBUG and lower, or to log warnings only
            **kwargs: No-Op keyword arguments for compatibility with config connection availability checks

        """
        if not importlib.util.find_spec("duckdb_engine"):
            logger.warning("The sqlalchemy duckdb_engine is not available")
            return False

        default_url_callable = cls.get_default_config()["url"]
        duckdb_url = url or default_url_callable()

        try:
            cls.verify_url_string(duckdb_url)
        except CacheParameterValidationException as e:
            logger.info(f"DuckDB is not available for connection at the provided URI: {e}")
            return False

        available = super().is_available(url=duckdb_url, verbose=verbose, **kwargs)

        return available


__all__ = ["SQLAlchemyStorage", "DuckDBStorage"]
