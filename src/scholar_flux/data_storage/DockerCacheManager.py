import os
import logging
from typing import Optional, Dict, Any

from .base import DataCacheManager
from .postgres_cache_manager import PostgresCacheManager
from .redis_cache_manager import RedisCacheManager
from .sqlite_cache_manager import SQLiteCacheManager
from .config_loader import ExtendedConfigLoader

# Initialize logger
logger = logging.getLogger(__name__)

class DockerDataCacheManager(DataCacheManager):
    def __init__(self) -> None:
        logger.info("Initializing DockerDataCacheManager...")
        
        # Load configuration using ExtendedConfigLoader
        self.config_loader = ExtendedConfigLoader(environment=os.getenv('ENVIRONMENT', 'development'))
        self.config_loader.load_config(reload_env=True)
        
        # Fetch storage backend and initialize the parent class
        storage_backend = self.config_loader.config.get("DATA_STORAGE_BACKEND", "in_memory")
        logger.info(f"Using storage backend: {storage_backend}")
        
        super().__init__()
        self.cache = self._create_cache_manager(storage_backend)
        logger.info(f"Cache manager initialized with backend: {storage_backend}")

    def _create_cache_manager(self, storage_backend: str) -> Any:
        """
        Create and return the appropriate cache manager based on the storage backend.
        """
        if storage_backend == "postgres":
            logger.debug("Initializing PostgreSQL cache manager...")
            # Read connection details from environment variables
            db_config = {
                "host": self.config_loader.config.get("POSTGRES_HOST"),
                "port": self.config_loader.config.get("POSTGRES_PORT"),
                "user": self.config_loader.config.get("POSTGRES_USER"),
                "password": self.config_loader.config.get("POSTGRES_PASSWORD"),
                "database": self.config_loader.config.get("POSTGRES_DATABASE"),
            }
            logger.debug(f"PostgreSQL config: {db_config}")
            return PostgresCacheManager(db_config)
        elif storage_backend == "redis":
            logger.debug("Initializing Redis cache manager...")
            # Read connection details from environment variables
            redis_config = {
                "host": self.config_loader.config.get("REDIS_HOST"),
                "port": self.config_loader.config.get("REDIS_PORT"),
                "db": self.config_loader.config.get("REDIS_DB", 0),  # Default DB 0
            }
            logger.debug(f"Redis config: {redis_config}")
            return RedisCacheManager(redis_config)
        elif storage_backend == "sqlite":
            logger.debug("Initializing SQLite cache manager...")
            # Read SQLite database path from environment variables
            db_path = self.config_loader.config.get("SQLITE_DB_PATH", "default.sqlite")
            logger.debug(f"SQLite DB path: {db_path}")
            return SQLiteCacheManager(db_path)
        else:
            logger.error(f"Unsupported storage backend: {storage_backend}")
            raise ValueError(f"Unsupported storage backend: {storage_backend}")

# Example usage in your Dockerized app:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data_storage_manager = DockerDataCacheManager()
    # Use data_storage_manager methods to interact with the cache

