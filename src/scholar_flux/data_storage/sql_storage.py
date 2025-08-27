import logging
from typing import Any, List, Dict, Optional, TYPE_CHECKING

from scholar_flux.utils.encoder import CacheDataEncoder
from scholar_flux.data_storage.base import ABCStorage
from scholar_flux.package_metadata import get_default_writable_directory
from scholar_flux.exceptions import SQLAlchemyImportError  # Custom exception for missing SQLAlchemy

import cattrs

logger = logging.getLogger(__name__)

# SQLAlchemy import logic for type checking and runtime
if TYPE_CHECKING:
    from sqlalchemy import create_engine, Column, String, Integer, JSON, exc, func
    from sqlalchemy.orm import DeclarativeBase, sessionmaker
    SQLALCHEMY_AVAILABLE = True
else:
    try:
        from sqlalchemy import create_engine, Column, String, Integer, JSON, exc, func
        from sqlalchemy.orm import DeclarativeBase, sessionmaker
        SQLALCHEMY_AVAILABLE = True
    except ImportError:
        # Dummies for names so code still parses, but using stubs or Nones for runtime
        create_engine = None
        def Column(*args, **kwargs): None  # type: ignore
        String = Integer = JSON = exc = func = None
        DeclarativeBase = object  # type: ignore
        sessionmaker = None
        SQLALCHEMY_AVAILABLE = False

# Define ORM classes if SQLAlchemy is available or for type checking
if TYPE_CHECKING or SQLALCHEMY_AVAILABLE:
    class Base(DeclarativeBase):  # type: ignore
        pass

    class CacheTable(Base):  # type: ignore
        __tablename__ = 'cache'
        id = Column(Integer, primary_key=True, autoincrement=True)
        key = Column(String, unique=True, nullable=False)
        cache = Column(JSON, nullable=False)
else:
    # Runtime stubs so code can be parsed, but will error if actually used
    Base = None  # type: ignore
    CacheTable = None  # type: ignore

class SQLAlchemyStorage(ABCStorage):

    DEFAULT_NAMESPACE: Optional[str] = None
    DEFAULT_CONFIG: Dict[str, Any] = {
         'url': lambda: 'sqlite:///' + str(get_default_writable_directory('package_cache') / 'data_store.sqlite'),
        'echo': False
    }

    def __init__(self, url: Optional[str] = None,
                 namespace: Optional[str] = None,
                 ttl: None = None,
                 **sqlalchemy_config) -> None:
        """
        Initialize the SQLAlchemy storage backend and connect to the server indicated via the `url` parameter.
        This class uses the innate flexibility of SQLAlchemy to support backends such as SQLite, Postgres, DuckDB, etc.

        Args:
            url (Optional[str]): Database connection string. This can be provided positionally or as a keyword argument.
            namespace (Optional[str]): The prefix associated with each cache key. By default, this is None.
            ttl (None): Ignored. Included for interface compatibility; not implemented.
            **sqlalchemy_config: Additional SQLAlchemy engine/session options passed to sqlalchemy.create_engine
                Typical parameters include the following:
                    url (str): Indicates what server to connect to. Defaults to sqlite in the package directory.
                    echo (bool): Indicates whether to show the executed SQL queries in the console.
        """

        if not SQLALCHEMY_AVAILABLE:
            raise SQLAlchemyImportError

        sqlalchemy_config['url'] = url or self.DEFAULT_CONFIG['url']()
        sqlalchemy_config['echo'] = (sqlalchemy_config.get('echo')
                                     if isinstance(sqlalchemy_config.get('echo'), bool)
                                     else self.DEFAULT_CONFIG['echo'])

        self.config: dict = sqlalchemy_config
        self.engine = create_engine(**self.config)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.converter = cattrs.Converter()
        self.namespace = namespace or self.DEFAULT_NAMESPACE

        if ttl:
            logger.warning("TTL is not enabled for SQLAlchemyStorage. Skipping")
        self.ttl = None

    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve the value associated with the provided key from cache.

        Args:
            key (str): The key used to fetch the stored data from cache.

        Returns:
            Any: The value returned is deserialized JSON object if successful. Returns None
                if the key does not exist.
        """
        with self.Session() as session:
            try:
                namespace_key = self._prefix(key)
                record = session.query(CacheTable).filter(CacheTable.key == namespace_key).first()
                if record:
                    return CacheDataEncoder.decode(self.converter.structure(record.cache, dict))
                return None
            except exc.SQLAlchemyError as e:
                logger.error(f"Error retrieving key {key}: {e}")
                return None

    def retrieve_all(self) -> Dict[str, Any]:
        """
        Retrieve all records from cache.

        Returns:
            dict: Dictionary of key-value pairs. Keys are original keys,
                values are JSON deserialized objects.
        """
        with self.Session() as session:
            cache = {}
            try:
                records = session.query(CacheTable).all()
                cache = {str(record.key): CacheDataEncoder.decode(self.converter.structure(record.cache, dict))
                         for record in records
                         if not self.namespace or str(record.key).startswith(self.namespace)}
            except exc.SQLAlchemyError as e:
                logger.error(f"Error retrieving all records: {e}")
            return cache

    def retrieve_keys(self) -> List[str]:
        """
        Retrieve all keys for records from cache .

        Returns:
            list: A list of all keys saved via SQL.
        """

        with self.Session() as session:
            try:
                keys = [str(record.key) for record in session.query(CacheTable).all() if not self.namespace or str(record.key).startswith(self.namespace)]
            except exc.SQLAlchemyError as e:
                logger.error(f"Error retrieving keys: {e}")
                keys = []
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
        with self.Session() as session:
            try:
                namespace_key = self._prefix(key)
                structured_data = self.converter.unstructure(CacheDataEncoder.encode(data))
                record = session.query(CacheTable).filter(CacheTable.key == namespace_key).first()
                if record:
                    record.cache = structured_data
                else:
                    record = CacheTable(key=namespace_key, cache=structured_data)
                    session.add(record)
                session.commit()

            except exc.SQLAlchemyError as e:
                logger.error(f"Error updating key {key}: {e}")
                session.rollback()

    def delete(self, key: str) -> None:
        """
        Delete the value associated with the provided key from cache.

        Args:
            key (str): The key used associated with the stored data from cache.

        """
        with self.Session() as session:
            try:
                namespace_key = self._prefix(key)
                record = session.query(CacheTable).filter(CacheTable.key == namespace_key).first()
                if record:
                    session.delete(record)
                    session.commit()
            except exc.SQLAlchemyError as e:
                logger.error(f"Error deleting key {key}: {e}")
                session.rollback()

    def delete_all(self) -> None:
        """
        Delete all records from cache that match the current namespace prefix.
        """
        with self.Session() as session:
            try:
                if self.namespace:
                    num_deleted = session.query(CacheTable).filter(CacheTable.key.startswith(self.namespace)).delete()
                    session.commit()
                else:
                    num_deleted = session.query(CacheTable).delete()
                    session.commit()
                    logger.debug(f"Deleted {num_deleted} records.")
            except exc.SQLAlchemyError as e:
                logger.error(f"Error deleting all records: {e}")
                session.rollback()

    def verify_cache(self,key: str) -> bool:
        """
        Check if specific cache key exists.

        Args:
            key (str): The key to check its presence in the SQL storage backend.

        Returns:
            bool: True if the key is found otherwise False.
        Raises:
            ValueError: If provided key is empty or None.
        """

        if not key:
            raise ValueError(f"Key invalid. Received {key}")
        return self.retrieve(key) is not None
