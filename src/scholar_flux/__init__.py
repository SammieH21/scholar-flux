import urllib3
import re
from .utils.logger import MaskAPIKeyFilter

def initialize_package(log=True):
    from .utils import setup_logging
    from .utils import config_settings
    if log:
        setup_logging()
        urllib3_logger = urllib3.connectionpool.log
        urllib3_logger.addFilter(MaskAPIKeyFilter())
    config_settings.load_config(reload_env=True)
    

    return config_settings.config

config=initialize_package()

from .utils import  SessionManager
from .data_storage import  DataCacheManager, SQLAlchemyCacheStorage#, RedisCacheManager, SQLiteCacheManager, PostgresCacheManager
from .data import  DataParser, DataProcessor, DataFormatter, DataExtractor
from .api import SearchAPI, BaseAPI, ResponseValidator,  ResponseCoordinator, SearchCoordinator
# ProcessingCacheManager,


