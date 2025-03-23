
from ..exceptions import PostgresImportError
from requests import Response
from .base import DataCacheManager
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.sql as sql

    class PostgresCacheManager(DataCacheManager):
        # ... (Your __init__ and _create_table_if_not_exists methods ) ...

        def _create_processed_articles_table(self):
            with self.conn.cursor() as cursor:
                cursor.execute(sql.SQL("""
                    CREATE TABLE IF NOT EXISTS processed_articles (
                        id SERIAL PRIMARY KEY,
                        cache_key TEXT REFERENCES {cache_table} (cache_key) ON DELETE CASCADE,
                        article_data JSONB 
                    )
                """).format(cache_table=sql.Identifier(self.table_name)))
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
            # ... (Your raw_response handling ) ...

            with self.conn.cursor() as cursor:
                # Insert or update the batch metadata in the original table
                cursor.execute(sql.SQL("""
                    INSERT INTO {table} (cache_key, response_hash, raw_response, parsed_response, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        response_hash = EXCLUDED.response_hash,
                        raw_response = EXCLUDED.raw_response,
                        parsed_response = EXCLUDED.parsed_response,
                        metadata = EXCLUDED.metadata
                """).format(table=sql.Identifier(self.table_name)),
                (cache_key, self.generate_response_hash(response), raw_response, parsed_response, metadata))

                # Insert each processed article into the new table
                for article in processed_response:
                    cursor.execute(sql.SQL("""
                        INSERT INTO processed_articles (cache_key, article_data)
                        VALUES (%s, %s)
                    """), (cache_key, article))  
                    
                self.conn.commit()

    # ... (Your retrieve and verify_cache methods might need minor adjustments 
    # to fetch from both tables if you want to retrieve everything together)

except ImportError as e:
    class PostgresCacheManager:
        def __init__(self,*args,**kwargs):
            raise PostgresImportError

