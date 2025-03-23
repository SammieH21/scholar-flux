
import json

from ..exceptions import RedisImportError
from .base import DataCacheManager
from typing import Any, Dict, Optional
from requests import Response

import  logging
logger = logging.getLogger(__name__)
try:
    import redis
    class RedisCacheManager(DataCacheManager):
        def __init__(self, redis_config: Dict[str, Any]):
            super().__init__(cache_storage={})
            self.redis_client = redis.Redis(**redis_config)

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
                'response_hash': self.generate_response_hash(response),
                'raw_response': response.content if store_raw else None,
                'parsed_response': parsed_response,
                'processed_response': processed_response,
                'metadata': metadata
            }
            self.redis_client.set(cache_key, json.dumps(cache_data))
            logger.debug(f"Cache updated for key: {cache_key}")

        def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
            cache_data = self.redis_client.get(cache_key)
            if cache_data:
                logger.debug(f"Retrieved record for key {cache_key}...")
                return json.loads(cache_data)
            else:
                logger.warning(f"Record for key {cache_key} not found...")
                return None

        def verify_cache(self, cache_key: str) -> bool:
            exists = self.redis_client.exists(cache_key)
            if exists:
                logger.info(f"Cache hit for key: {cache_key}")
                return True
            logger.info(f"No cached data for key: '{cache_key}'")
            return False

except ImportError as e:
    class RedisCacheManager:
        def __init__(self,*args,**kwargs):
            raise RedisImportError
