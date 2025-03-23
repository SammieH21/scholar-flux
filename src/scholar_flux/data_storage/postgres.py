from .base import DataCacheManager
from typing import Any, Dict, Optional
from requests import Response

from ..exceptions import PostgresImportError

import  logging
logger = logging.getLogger(__name__)
try:
    import psycopg2
    from psycopg2 import sql

    class PostgresCacheManager(DataCacheManager):
        def __init__(self, db_config: Dict[str, Any], table_name: str = 'cache'):
            super().__init__(cache_storage={})
            self.conn = psycopg2.connect(**db_config)
            self.table_name = table_name
            self._create_table_if_not_exists()

        def _create_table_if_not_exists(self) -> None:
            with self.conn.cursor() as cursor:
                cursor.execute(sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {table} (
                        cache_key TEXT PRIMARY KEY,
                        response_hash TEXT,
                        raw_response BYTEA,
                        parsed_response BYTEA,
                        processed_response BYTEA,
                        metadata JSONB
                    )
                """).format(table=sql.Identifier(self.table_name)))
                self.conn.commit()

        def update_cache(
            self,
            cache_key: str,
            response: Response,
            store_raw: bool = False,
            metadata: Optional[Dict[str, Any]] = None,
            parsed_response: Optional[Any] = None,
            processed_response: Optional[Any] = None
        ) -> None:
            raw_response = response.content if store_raw else None
            with self.conn.cursor() as cursor:
                cursor.execute(sql.SQL("""
                    INSERT INTO {table} (cache_key, response_hash, raw_response, parsed_response, processed_response, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        response_hash = EXCLUDED.response_hash,
                        raw_response = EXCLUDED.raw_response,
                        parsed_response = EXCLUDED.parsed_response,
                        processed_response = EXCLUDED.processed_response,
                        metadata = EXCLUDED.metadata
                """).format(table=sql.Identifier(self.table_name)),
                (cache_key, self.generate_response_hash(response), raw_response, parsed_response, processed_response, metadata))
                self.conn.commit()
            logger.debug(f"Cache updated for key: {cache_key}")

        def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
            with self.conn.cursor() as cursor:
                cursor.execute(sql.SQL("SELECT * FROM {table} WHERE cache_key = %s").format(table=sql.Identifier(self.table_name)), (cache_key,))
                result = cursor.fetchone()
            if result:
                logger.debug(f"Retrieved record for key {cache_key}...")
                return {
                    'cache_key': result[0],
                    'response_hash': result[1],
                    'raw_response': result[2],
                    'parsed_response': result[3],
                    'processed_response': result[4],
                    'metadata': result[5]
                }
            else:
                logger.warning(f"Record for key {cache_key} not found...")
                return None

        def verify_cache(self, cache_key: str) -> bool:
            with self.conn.cursor() as cursor:
                cursor.execute(sql.SQL("SELECT EXISTS(SELECT 1 FROM {table} WHERE cache_key = %s)").format(table=sql.Identifier(self.table_name)), (cache_key,))
                exists = cursor.fetchone()[0]
            if exists:
                logger.info(f"Cache hit for key: {cache_key}")
                return True
            logger.info(f"No cached data for key: '{cache_key}'")
            return False

except ImportError as e:
    class PostgresCacheManager:
        def __init__(self,*args,**kwargs):
            raise PostgresImportError
