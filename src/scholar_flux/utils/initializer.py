# /utils/initializer.py
"""The scholar_flux.utils.initializer.py module is used within the scholar_flux package to kickstart the initialization
of the scholar_flux package on import.

Several key steps are performed via the use of the initializer: 1) Environment variables are imported using the
ConfigLoader 2) The Logger is subsequently set up for the scholar_flux API package 3) The package level masker is
subsequently set up to enable sensitive data to be redacted from logs

"""
from typing import Optional, Any
import logging
import scholar_flux.security as security
from pprint import pformat
import warnings
from scholar_flux.utils.logger import setup_logging
from scholar_flux.exceptions import PackageInitializationError
from scholar_flux.utils.config_loader import ConfigLoader
from pathlib import Path

config_settings = ConfigLoader()


def initialize_package(
    log: bool = True,
    env_path: Optional[str | Path] = None,
    config_params: Optional[dict[str, Any]] = None,
    logging_params: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], logging.Logger, security.SensitiveDataMasker]:
    """Function used for orchestrating the initialization of the config, log settings, and masking for scholar_flux.

    This function imports a '.env' configuration file at the specified location if it exists. Otherwise, `scholar_flux`
    will look for a `.env` file in the default locations if available. If no .env configuration file is found, then only
    package defaults and available OS environment variables are used.

    This function can also be used for dynamic re-initialization of configuration parameters and logging. The
    `config_params` are sent as keyword arguments to the scholar_flux.utils.ConfigSettings.load_config method.
    `logging_paras` are used as keyword arguments to the scholar_flux.utils.setup_logging method to set up
    logging settings and handlers.

    Args:
        log (bool): A `True`/`False` flag that determines whether to enable or disable logging.
        env_path (Optional[str | Path]):
            The file path indicating from where to load the environment variables, if provided.
        config_params (Optional[Dict]):
            A dictionary allowing for the specification of configuration parameters when attempting to load environment
            variables from a config. Useful for loading API keys from environment variables for later use.
        logging_params (Optional[Dict]):
            A dictionary allowing users to specify options for package-level logging with custom logic. Log settings are
            loaded from the OS environment or an .env file when available, with precedence given to .env files. These
            settings, when loaded, override the default ScholarFlux logging configuration. Otherwise,
            ScholarFlux uses a log-level of `WARNING` by default.

    Returns:
        Tuple[Dict[str, Any], logging.Logger, scholar_flux.security.SensitiveDataMasker]:
            A tuple containing the configuration dictionary and the initialized logger.

    Raises:
        PackageInitializationError: If there are issues with loading the configuration or initializing the logger.

    """
    if config_params is not None and not isinstance(config_params, dict):
        raise PackageInitializationError(
            "An error occurred in the reinitialization of scholar_flux: "
            f"`config_params` must be a dictionary, but received {type(config_params)}."
        )

    if logging_params is not None and not isinstance(logging_params, dict):
        raise PackageInitializationError(
            "An error occurred in the reinitialization of scholar_flux: "
            f"`logging_params` must be a dictionary, but received {type(logging_params)}."
        )

    logger = (
        logging_params["logger"]
        if isinstance(logging_params, dict) and isinstance(logging_params.get("logger"), logging.Logger)
        else logging.getLogger("scholar_flux")
    )

    masker = security.SensitiveDataMasker()
    masking_filter = security.MaskingFilter(masker)

    # Attempt to load configuration parameters from the provided env file
    config_params_dict: dict = {"reload_env": True}
    config_params_dict.update(config_params or {})

    if env_path:
        config_params_dict["env_path"] = env_path

    # if configuration parameters are provided by the user, load with verbose settings:
    config_params_dict.setdefault("verbose", bool(config_params or env_path))

    try:
        config_settings.load_config(**config_params_dict)
    except Exception as e:
        warnings.warn(
            "Failed to load the configuration settings for the scholar_flux package. Falling back to the default "
            f"configuration settings: {e}"
        )

    # turn off file rotation logging if not enabled
    log_file = (
        config_settings.get("SCHOLAR_FLUX_LOG_FILE", "application.log")
        if config_settings.get("SCHOLAR_FLUX_ENABLE_LOGGING") in ("T", "TRUE", "1")
        else None
    )

    propagate_logs = config_settings.get("SCHOLAR_FLUX_PROPAGATE_LOGS") not in ("F", "FALSE", "0")

    # for logging resolution, fallback to WARNING
    log_level = getattr(logging, config_settings.get("SCHOLAR_FLUX_LOG_LEVEL", ""), logging.WARNING)

    # declares the default parameters from scholar_flux after loading configuration environment variables
    logging_params_dict: dict = {
        "logger": logger,
        "log_directory": config_settings.get("SCHOLAR_FLUX_LOG_DIRECTORY"),
        "log_file": log_file,
        "log_level": log_level,
        "logging_filter": masking_filter,
        "propagate_logs": propagate_logs,
    }

    logging_params_dict.update(logging_params or {})

    try:
        if log:
            # initializes logging with custom defaults
            setup_logging(**logging_params_dict)
        else:
            # ensure the logger does not output if logging is turned off
            logger.handlers = []
            logger.addHandler(logging.NullHandler())
    except Exception as e:
        raise PackageInitializationError(f"Failed to initialize the logger for the scholar_flux package: {e}")

    logger.debug(
        "Loaded Scholar Flux with the following parameters:\n"
        f"config_params={pformat(config_params_dict)}\n"
        f"logging_params={pformat(logging_params_dict)}"
    )

    return config_settings.config, logger, masker


__all__ = ["initialize_package", "config_settings"]
