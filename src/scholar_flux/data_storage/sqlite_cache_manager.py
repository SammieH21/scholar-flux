import sqlite3
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)

    def execute(self, query: str, params: tuple = ()):
        with self.conn:
            self.conn.execute(query, params)

    def fetchall(self, query: str, params: tuple = ()) -> list:
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def fetchone(self, query: str, params: tuple = ()) -> tuple:
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
# cache_manager.py

# cache_manager.py

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from requests import Response
#from .database import DatabaseManager
from .base import DataCacheManager
from .utils import generate_response_hash

logger = logging.getLogger(__name__)

class CacheManager(DataCacheManager):
    def __init__(self, db_path: str, cache_table_name: str = 'processing_cache_table', processed_table_name: str = 'processed_table'):
        super().__init__(cache_storage={})
        self.db = DatabaseManager(db_path)
        self.cache_table_name = cache_table_name
        self.processed_table_name = processed_table_name
        self._create_tables_if_not_exists()

    def _create_tables_if_not_exists(self) -> None:
        self.db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.cache_table_name} (
                cache_key TEXT PRIMARY KEY,
                response_hash TEXT,
                raw_response BLOB,
                parsed_response BLOB,
                metadata TEXT
            )
        """)
        self.db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.processed_table_name} (
                id VARCHAR(50) PRIMARY KEY,
                cache_key TEXT,
                article_data BLOB,
                FOREIGN KEY(cache_key) REFERENCES {self.cache_table_name}(cache_key) ON DELETE CASCADE
            )
        """)

    def update_cache(self, cache_key: str, response: Response, store_raw: bool = False, metadata: Optional[Dict[str, Any]] = None, parsed_response: Optional[Any] = None, processed_response: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Updates the cache storage with new data.

        Args:
        - cache_key: A unique identifier for the cached data.
        - response: The API response object.
        - store_raw: Optional; A boolean indicating whether to store the raw response. Defaults to False.
        - metadata: Optional; Additional metadata associated with the cached data. Defaults to None.
        - parsed_response: Optional; The response data parsed into a structured format. Defaults to None.
        - processed_response: Optional; The response data processed for specific use. Defaults to None.
        """
        raw_response = response.content if store_raw else None
        self.db.execute(
            f"""
            REPLACE INTO {self.cache_table_name}
                (cache_key, response_hash, raw_response, parsed_response, metadata) 
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                generate_response_hash(response),
                str(raw_response),
                json.dumps(parsed_response) if parsed_response else None,
                json.dumps(metadata)
            ),
        )
        if processed_response:
            fmt_processed_records = [{'article_data': json.dumps(record), 'cache_key': cache_key, 'id': f"{cache_key}_{i}"} for i, record in enumerate(processed_response)]
            for record in fmt_processed_records:
                self.db.execute(
                    f"""
                    REPLACE INTO {self.processed_table_name}
                        (cache_key, article_data, id) 
                    VALUES (?, ?, ?)
                    """,
                    (
                        record['cache_key'],
                        record['article_data'],
                        record['id'],
                    ),
                )
        logger.debug(f"Cache updated for key: {cache_key}")

    def _clear(self, cache_key: Optional[List[str]] = None, table_name: Optional[str] = None, cursor=None) -> None:
        """
        Clears cache entries from the specified table.

        Args:
        - cache_key: Optional; A unique identifier for the cached data. Defaults to None.
        - table_name: Optional; The name of the table to clear entries from. Defaults to None.
        - cursor: Optional; The database cursor to use. Defaults to None.
        """
        cursor = cursor or self.db.conn.cursor()
        if cache_key:
            if self.verify_cache(cache_key=cache_key, table_name=table_name, cursor=cursor):
                logger.debug(f"Removing record for cache_key={cache_key} from table {table_name}")
                cursor.execute(f"DELETE FROM {table_name} WHERE cache_key in ?", (cache_key,))
            else:
                logger.debug("No records removed")
        else:
            logger.debug(f"Removing all cached records from table {table_name}")
            cursor.execute(f"DELETE FROM {table_name} WHERE 1=1")

    def delete_all_from_cache(self, cursor=None) -> None:
        """
        Deletes all cache entries from all tables.

        Args:
        - cursor: Optional; The database cursor to use. Defaults to None.
        """
        cursor = cursor or self.db.conn.cursor()
        logger.debug("Removing all records from cache tables")
        self._clear(table_name=self.cache_table_name, cursor=cursor)
        self._clear(table_name=self.processed_table_name, cursor=cursor)

    def delete_from_cache(self, cache_keys: List[str], cursor=None) -> None:
        """
        Deletes specific cache entries.

        Args:
        - cache_keys: A list of cache keys to delete.
        - cursor: Optional; The database cursor to use. Defaults to None.
        """
        cursor = cursor or self.db.conn.cursor()
        logger.debug(f"Deleting cache keys: {', '.join(cache_keys)} from tables.")
        for cache_key in cache_keys:
            self._clear(cache_key=cache_key, table_name=self.cache_table_name, cursor=cursor)
            self._clear(cache_key=cache_key, table_name=self.processed_table_name, cursor=cursor)

    def _count_records(self, table_name: str, cache_key: Optional[str] = None, cursor=None) -> int:
        """
        Counts the number of records in a table, optionally filtering by cache key.

        Args:
        - table_name: The name of the table to count records in.
        - cache_key: Optional; A unique identifier for the cached data. Defaults to None.
        - cursor: Optional; The database cursor to use. Defaults to None.

        Returns:
        - int: The number of records in the table.
        """
        cursor = cursor or self.db.conn.cursor()
        if cache_key:
            return cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE cache_key = ?", (cache_key,)).fetchone()[0]
        else:
            return cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    def _lookup(self, cache_key: Optional[str], table_name: str, var: str = 'article_data', cursor=None) -> List[Tuple]:
        """
        Looks up data in a table by cache key.

        Args:
        - cache_key: Optional; A unique identifier for the cached data. Defaults to None.
        - table_name: The name of the table to look up data in.
        - var: Optional; The column to retrieve. Defaults to 'article_data'.
        - cursor: Optional; The database cursor to use. Defaults to None.

        Returns:
        - List[Tuple]: A list of tuples containing the retrieved data.
        """
        cursor = cursor or self.db.conn.cursor()
        if cache_key:
            return cursor.execute(f"SELECT {var} FROM {table_name} WHERE cache_key = ?", (cache_key,)).fetchall()
        else:
            return cursor.execute(f"SELECT {var} FROM {table_name}").fetchall()

    def verify_cache(self, cache_key: str, table_name: Optional[str] = None, cursor=None) -> bool:
        """
        Verifies if a cache entry exists for a given key.

        Args:
        - cache_key: A unique identifier for the cached data.
        - table_name: Optional; The name of the table to verify the cache in. Defaults to None.
        - cursor: Optional; The database cursor to use. Defaults to None.

        Returns:
        - bool: True if the cach
        """

# utils.py

import hashlib
from urllib.parse import urlparse
from requests import Response

def generate_fallback_cache_key(response: Response) -> str:
    parsed_url = urlparse(response.url)
    simplified_url = f"{parsed_url.netloc}{parsed_url.path}"
    status_code = response.status_code
    return hashlib.sha256(f"{simplified_url}_{status_code}".encode()).hexdigest()

def generate_response_hash(response: Response) -> str:
    return hashlib.sha256(response.content).hexdigest()

