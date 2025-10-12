# /utils/initializer.py
"""
The scholar_flux.utils.initializer.py module is used within the scholar_flux package to kickstart the initialization
of the scholar_flux package on import. Several key steps are performed via the use of the initializer:
    1) Environment variables are imported using the ConfigLoader
    2) The Logger is subsequently set up for the scholar_flux API package
    3) The package level masker is subsequently set up to enable sensitive data to be redacted from logs
"""
from typing import Optional, Any
import logging
import scholar_flux.security as security
from pprint import pformat
from scholar_flux.utils.logger import setup_logging
from scholar_flux.utils.config_loader import ConfigLoader

config_settings = ConfigLoader()


def initialize_package(
    log: bool = True,
    env_path: Optional[str] = None,
    config_params: Optional[dict[str, Any]] = None,
    logging_params: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], logging.Logger, security.SensitiveDataMasker]:
    """
    Function used for initializing the scholar_flux package
    Imports a '.env' config file in the event that it is available at a default location
    Otherwise loads the default settings of the package.

    Also allows for dynamic re-initialization of configuration parameters and logging.
    config_parameters correspond to the scholar_flux.utils.ConfigSettings.load_config method.
    logging_parameters correspond to the scholar_flux.utils.setup_logging method for logging settings and handlers.

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

    # Attempt to load configuration parameters from the provided env file
    config_params_dict: dict = {"reload_env": True}
    config_params_dict.update(config_params or {})

    if env_path:
        config_params_dict["env_path"] = env_path

    # if the original config_params is empty/None, load with verbose settings:
    verbose = bool(config_params_dict)
    try:
        config_settings.load_config(**config_params_dict, verbose=verbose)
        config = config_settings.config
    except Exception as e:
        raise ValueError(f"Failed to load the configuration settings for the scholar_flux package: {e}")

    # declares the default parameters from scholar_flux after loading configuration environment variables
    logging_params_dict: dict = {
        "logger": logger,
        "log_directory": config.get("SCHOLAR_FLUX_LOG_DIRECTORY"),
        "log_file": config.get("SCHOLAR_FLUX_LOG_FILE", "application.log"),
        "log_level": config.get("SCHOLAR_FLUX_LOG_LEVEL", logging.DEBUG),
        "logging_filter": masking_filter,
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


__all__ = ["initialize_package", "config_settings"]
