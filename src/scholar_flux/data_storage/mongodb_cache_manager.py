import json
from typing import Dict, Any, List, Optional, Annotated
from ..exceptions import MongoDBImportError
from .base import DataCacheManager
from typing import Any, Dict, Optional
from requests import Response

import  logging
logger = logging.getLogger(__name__)
try:
    import pymongo
    class MongoDBCacheManager(DataCacheManager):

        DEFAULT_CONFIG: dict = {'host':'localhost','port':27017,'db':'storage_manager_db', 'collection':'result_page'}

        def __init__(self, mongo_config: Optional[Dict[str, Any]]=None):
            super().__init__(cache_storage={})
            self.config = dict(**self.DEFAULT_CONFIG, **mongo_config) if mongo_config else self.DEFAULT_CONFIG
            self.mongo_client = pymongo.MongoClient(host=self.config["host"], port=self.config["port"])
            self.client_db=self.mongo_client[self.config['db']]
            self.collection=self.client_db[self.config['collection']]

            self.db_exists(db=self.config.get("db"),
                           collection=self.config['collection'])

        def db_exists(self,db,collection=''):
            if not db in self.mongo_client.list_database_names():
                logger.info(f"Initializing database: {db} for collection {collection}")

        def update_cache(
            self,
            cache_key: str,
            response: Response,
            store_raw: bool = False,
            metadata: Optional[Dict[str, Any]] = None,
            parsed_response: Optional[Any] = None,
            processed_response: Optional[Any] = None
        ) -> None:


            cache_data = {
                'cache_key': cache_key,
                'response_hash': self.generate_response_hash(response),
                'raw_response': response.content if store_raw else None,
                'parsed_response': parsed_response,
                'processed_response': processed_response,
                'metadata': metadata
            }
            self.collection.update_one({'cache_key':cache_key},
                                       {'$set':cache_data},upsert=True)
            logger.debug(f"Cache updated for key: {cache_key}")

        def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
            cache_data = self.collection.find_one({'cache_key':cache_key})
            if cache_data:
                logger.debug(f"Retrieved record for key {cache_data.pop('cache_key')}...")
                return cache_data
            else:
                logger.warning(f"Record for key {cache_key} not found...")
                return None

        def verify_cache(self, cache_key: str) -> bool:
            tot = self.collection.count_documents({'cache_key':cache_key})
            if tot>0:
                logger.info(f"Cache hit for key: {cache_key}")
                return True
            logger.info(f"No cached data for key: '{cache_key}'")
            return False

except ImportError as e:
    class MongoDBCacheManager:
        def __init__(self,*args,**kwargs):
            raise MongoDBImportError

