import urllib3
from typing import Optional, Any
import re
import logging
import scholar_flux.security as security

from scholar_flux.utils.logger import setup_logging
from pprint import pformat

def __getattr__(name):
    if name == "__version__":
        from scholar_flux.package_metadata import __version__
        return __version__
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

def initialize_package(log: bool=True,
                       env_path: Optional[str] = None,
                       config_params: Optional[dict[str, Any]] = None,
                       logging_params:Optional[dict[str, Any]] = None ) -> tuple[dict[str, Any], logging.Logger, security.SensitiveDataMasker]:
    """
    Function used for initializing the scholar_flux package
    Imports a '.env' config file in the event that it is available at a default location
    Otherwise loads the default settings of the package.

    Also allows for dynamic re-initialization of configuration parameters and logging.
    config_parameters correspond to the scholar_flux.utils.ConfigSettings.load_config method.
    logging_parameters correspond to the scholar_flux.utils.setup_logging method for logging settings and handlars.

    Args:
        config_params (Optional[dict]): A dictionary allowing for the specification of
                                        configuration parameters when attempting to
                                        load environment variables from a config.
                                        Useful for loading API keys from environment
                                        variables for later use.
        env_path (Optional[str]) The location indicating where to load the environment variables, if provided.
        logging_params (dict): Options for the creation of a logger with custom logic.
                               The logging used will be overwritten with the logging level from the loaded config
                               If available. Otherwise the log_level parameter is set to DEBUG by default.

    Returns:
        Tuple[Dict[str, Any], logging.Logger]: A tuple containing the configuration dictionary and the initialized logger.

    Raises:
        ValueError: If there are issues with loading the configuration or initializing the logger.
    """

    logger = logging.getLogger()

    masker = security.SensitiveDataMasker()
    masking_filter = security.MaskingFilter(masker)
    
    from scholar_flux.utils import setup_logging
    from scholar_flux.utils import config_settings


    # Attempt to load configuration parameters from the provided env file
    config_params_dict: dict= {'reload_env': True}
    config_params_dict.update(config_params or {})

    if env_path:
        config_params_dict['env_path'] = env_path

    # if the original config_params is empty/None, load with verbose settings:
    verbose = bool(config_params_dict)
    try:
        config_settings.load_config(**config_params_dict, verbose=verbose)
        config = config_settings.config
    except Exception as e:
        raise ValueError(f"Failed to load the configuration settings for the scholar_flux package: {e}")

    # declares the default parameters from scholar_flux after loading configuration environment variables
    logging_params_dict: dict={'logger':logger,
                               'log_directory': config.get('SCHOLAR_FLUX_LOG_DIRECTORY'),
                               'log_file': config.get('SCHOLAR_FLUX_LOG_FILE', 'application.log'),
                               'log_level': config.get('SCHOLAR_FLUX_LOG_LEVEL',logging.DEBUG),
                               'logging_filter': masking_filter
                              }

    logging_params_dict.update(logging_params or {})

    try:
        if log:
            # initializes logging with custom defaults
            setup_logging(**logging_params_dict)
        else:
            # ensure the logger does not output if logging is turned off
            logger.addHandler(logging.NullHandler())
    except Exception as e:
        raise ValueError(f"Failed to initialize the logging for the scholar_flux package: {e}")

    logging.debug(
        "Loaded Scholar Flux with the following parameters:\n"
        f"config_params={pformat(config_params_dict)}\n"
        f"logging_params={pformat(logging_params_dict)}"
    )

    return config_settings.config, logger, masker

config, logger, masker = initialize_package()

from scholar_flux.sessions import SessionManager, CachedSessionManager
from scholar_flux.data_storage import  DataCacheManager, SQLAlchemyStorage, RedisStorage, InMemoryStorage, MongoDBStorage, NullStorage
from scholar_flux.data import  DataParser, DataExtractor, RecursiveDataProcessor, PathDataProcessor, DataProcessor
from scholar_flux.api import SearchAPI, BaseAPI, ResponseValidator,  ResponseCoordinator, SearchCoordinator

__all__ = ["__version__", "config", "logger"]
