# /api/utils/config_loader.py
"""
The scholar_flux.api.utils.config_loader is the primary configuration loader used by the scholar_flux package to
ensure that user-specified package default settings are registered via the use of environment variables.

The ConfigLoader is used alongside the scholar_flux.utils.initializer to fully initialize the scholar_flux
package with the chosen configuration. This includes the initialization of importing API keys as secret
strings, defining log levels, default API providers, etc.
"""
import os
import logging
from scholar_flux.package_metadata import get_default_writable_directory
from dotenv import set_key, load_dotenv, dotenv_values
import re
from pydantic import SecretStr

from pathlib import Path
from typing import Dict, Any, Optional, Union
from scholar_flux.security import SensitiveDataMasker

# Initialize logger
logging.basicConfig(level=logging.INFO)
config_logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Helper class used to load the configuration of the scholar_flux package on initialization to dynamically configure
    package options. Using the config loader with environment variables, the following settings can be defined
    at runtime.

        Package Level Settings:
            - SCHOLAR_FLUX_DEFAULT_PROVIDER: Defines the provider to use by default when creating a SearchAPI instance
        API_KEYS:
            - SPRINGER_NATURE_API_KEY: API Key used when retrieving academic data from Springer Nature
            - CROSSREF_API_KEY: API key used to retrieve academic metadata from Crossref (API key not required)
            - CORE_API_KEY: API key used to retrieve metadata and full-text publications from the CORE API
            - PUBMED_API_KEY: API key used to retrieve publications from the NIH PubMed database
        Session Cache:
            - SCHOLAR_FLUX_CACHE_DIRECTORY: defines where requests and response processing cache will be stored when
                                             using sqlite and similar cache storages
            - SCHOLAR_FLUX_CACHE_SECRET_KEY: defines the secret key used to create encrypted session cache for request
                                             retrieval
        Logging:
            - SCHOLAR_FLUX_LOG_DIRECTORY: defines where rotatable logs will be stored when logging is enabled
            - SCHOLAR_FLUX_LOG_LEVEL: defines the default log level used for package level logging during and after
                                      scholar_flux package initialization

    Examples:

        >>> from scholar_flux.utils import ConfigLoader
        >>> from pydantic import SecretStr
        >>> config_loader = ConfigLoader()
        >>> config_loader.load_config(reload_env=True)
        >>> api_key = '' # Your key goes here
        >>> if api_key:
        >>>     config_loader.config['CROSSREF_API_KEY'] = api_key
        >>> print(config_loader.env_path) # the default environment location when writing/replacing a env config
        >>> config_loader.save_config() # to save the full configuration in the default environment folder

    """

    DEFAULT_ENV_PATH: Path = (
        get_default_writable_directory(directory_type="env", default=Path(__file__).resolve().parent.parent) / ".env"
    )  # Default directory for the package env file

    # Values already present within the environment before loading
    DEFAULT_ENV: Dict[str, Any] = {
        "SPRINGER_NATURE_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("SPRINGER_NATURE_API_KEY")),
        "CROSSREF_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("CROSSREF_API_KEY")),
        "CORE_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("CORE_API_KEY")),
        "PUBMED_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("PUBMED_API_KEY")),
        "SCHOLAR_FLUX_CACHE_SECRET_KEY": SensitiveDataMasker.mask_secret(os.getenv("SCHOLAR_FLUX_CACHE_SECRET_KEY")),
        "SCHOLAR_FLUX_CACHE_DIRECTORY": os.getenv("SCHOLAR_FLUX_CACHE_DIRECTORY"),
        "SCHOLAR_FLUX_LOG_DIRECTORY": os.getenv("SCHOLAR_FLUX_LOG_DIRECTORY"),
        "SCHOLAR_FLUX_LOG_LEVEL": os.getenv("SCHOLAR_FLUX_LOG_LEVEL") or "DEBUG",
        "SCHOLAR_FLUX_DEFAULT_PROVIDER": os.getenv("SCHOLAR_FLUX_DEFAULT_PROVIDER") or "plos",
    }

    def __init__(self, env_path: Optional[Path | str] = None):
        """Utility class for loading environment variables from the operating system and .env files"""

        self.env_path: Path = self._process_env_path(env_path)
        self.config: Dict[str, Any] = self.DEFAULT_ENV.copy()  # Use a copy to avoid modifying the class attribute

    def try_loadenv(self, env_path: Optional[Path | str] = None, verbose: bool = False) -> Optional[Dict[str, Any]]:
        """
        Try to load environment variables from a specified .env file into the environment and return as a dict.
        """
        env_path = self._process_env_path(env_path or self.env_path)
        if load_dotenv(env_path):  # Load environment variables from a .env file
            return dotenv_values(env_path)
        else:
            if verbose:
                config_logger.debug(f"No environment file located at {env_path}. Loading defaults.")
            return {}

    def load_dotenv(
        self,
        env_path: Optional[Path | str] = None,
        replace_all: bool = False,
        verbose: bool = False,
    ) -> dict:
        """
        Retrieves a list of nonmissing environment variables from the current .env file that are non-null

        Args:
            env_path: Optional[Path | str]: Location of the .env file where env variables will be retrieved from
            replace_all: bool = False: Indicates whether all environment variables should be replaced vs. only non-missing variables
            verbose: bool = False: Flag indicating whether logging should be shown in the output

        Returns:
            dict: A dictionary of key-value pairs corresponding to environment variables
        """
        env_path = self._process_env_path(env_path or self.env_path)

        if verbose:
            config_logger.debug(f"Attempting to load environment file located at {env_path}.")

        env_config = self.try_loadenv(env_path, verbose=False)

        if env_config:
            config_env_variables = {
                k: self._guard_secret(v, k) for k, v in env_config.items() if replace_all or v is not None
            }
            return config_env_variables

        return {}

    @staticmethod
    def _guard_secret(
        value: Any,
        key: str | int,
        matches: list[str] | tuple = ("API_KEY", "SECRET", "MAIL"),
    ) -> Any | SecretStr:
        """
        Helper method to flag and guard the values of api keys, secrets, and likely email addresses by transforming
        them into secret strings if they are non-missing

        Args:
            value (Any): The value to convert to a string if its key contains any match
            key (str): The value to verify if it contains any match to keys containing API/SECRET/MAIL
            matches (str): The substrings used to indicate whether a secret should be guarded

        Returns:
            Any | SecretStr: The original type if the value is likely not a secret. otherwise returns a SecretStr

        """
        if isinstance(value, str) and matches is not None:
            return (
                SensitiveDataMasker.mask_secret(value)
                if re.search("|".join(matches), str(key)) and value is not None
                else value
            )
        return value

    def load_os_env(self, replace_all: bool = False, verbose: bool = False) -> dict:
        """
        Load any updated configuration settings from variables set within the system environment.
        The configuration setting must already exist in the config to be updated if available.
        Otherwise, the ConfigLoader.update_config method allows direct updates to the config settings.

        Args:
            replace_all: bool = False: Indicates whether all environment variables should be replaced vs. only non-missing variables
            verbose: bool = False: Flag indicating whether logging should be shown in the output

        Returns:
            dict: A dictionary of key-value pairs corresponding to environment variables
        """
        if verbose:
            config_logger.debug("Attempting to load updated settings from the system environment.")

        updated_env_variables = {
            k: self._guard_secret(os.environ.get(k), k)
            for k in self.config
            if replace_all or os.environ.get(k) is not None
        }
        return updated_env_variables

    def load_config(
        self,
        reload_env: bool = False,
        env_path: Optional[Path | str] = None,
        reload_os_env: bool = False,
        verbose: bool = False,
    ) -> None:
        """
        Load configuration settings from a .env file.
        Optionally attempt to reload newly set environment variables from the OS
        """

        os_config = self.load_os_env(verbose=verbose) if reload_os_env else {}
        dotenv_config = self.load_dotenv(env_path, verbose=verbose) if reload_env else {}

        config_env_variables = os_config | dotenv_config

        self.update_config(config_env_variables, verbose=verbose)

    def update_config(self, env_dict: dict[str, Any], verbose: bool = False) -> None:
        """
        Helper method for both logging and updating the config dictionary
        with the provided dictionary of environment variable key-value pairs
        """
        if verbose and env_dict:
            config_logger.debug("Updating the following variables into the config settings:", env_dict)
        self.config.update(env_dict)

    def save_config(self, env_path: Optional[Path | str] = None) -> None:
        """
        Save configuration settings to a .env file. Unmasks strings read as secrets if the are of the type,
        `SecretStr`.
        """
        env_path = env_path or self.env_path
        for key, value in self.config.items():
            if value is not None:
                self.write_key(key, SensitiveDataMasker.unmask_secret(value), env_path)

    def write_key(
        self,
        key_name: str,
        key_value: str,
        env_path: Optional[Path | str] = None,
        create: bool = True,
    ) -> None:
        """
        Write a key-value pair to a .env file.
        """
        env_path = self._process_env_path(env_path or self.env_path)
        try:
            if create and not env_path.exists():
                env_path.touch()
            set_key(str(env_path), key_name, key_value)
        except IOError as e:
            config_logger.error(f"Failed to create .env file at {env_path}: {e}")

    @classmethod
    def _process_env_path(cls, env_path: Optional[Union[str, Path]]) -> Path:
        """Try to load from the provided `env_path` variable first. Otherwise try to load from DEFAULT_ENV_PATH"""
        if not env_path:
            return cls.DEFAULT_ENV_PATH

        raw_env_path = Path(str(env_path))
        return raw_env_path.resolve() if raw_env_path.exists() else cls.DEFAULT_ENV_PATH

__all__ = ["ConfigLoader"]
