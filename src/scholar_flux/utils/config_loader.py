# /api/utils/config_loader.py
"""The scholar_flux.api.utils.config_loader is the primary configuration loader used by the scholar_flux package to
ensure that user-specified package default settings are registered via the use of environment variables.

The ConfigLoader is used alongside the scholar_flux.utils.initializer to fully initialize the scholar_flux package with
the chosen configuration. This includes the initialization of importing API keys as secret strings, defining log levels,
default API providers, etc.

"""
import os
import logging
import warnings
from scholar_flux.package_metadata import get_default_writable_directory
from dotenv import set_key, load_dotenv, dotenv_values
import re
from pydantic import SecretStr

from pathlib import Path
from typing import Dict, Any, Optional, Union
from scholar_flux.security import SensitiveDataMasker
from scholar_flux.utils.helpers import coerce_int, try_int

# Initialize logger
logging.basicConfig(level=logging.INFO)
config_logger = logging.getLogger(__name__)


class ConfigLoader:
    """Helper class used to load the configuration of the scholar_flux package on initialization to dynamically
    configure package options. Using the config loader with environment variables, the following settings can be defined
    at runtime.

        Package Level Settings:
            - SCHOLAR_FLUX_DEFAULT_PROVIDER: Defines the provider to use by default when creating a SearchAPI instance
        API_KEYS:
            - ARXIV_API_KEY: API key used when retrieving academic data from arXiv
            - OPEN_ALEX_API_KEY: API key used when retrieving academic data from OpenAlex
            - SPRINGER_NATURE_API_KEY: API key used when retrieving academic data from Springer Nature
            - CROSSREF_API_KEY: API key used to retrieve academic metadata from Crossref (API key not required)
            - CORE_API_KEY: API key used to retrieve metadata and full-text publications from the CORE API
            - PUBMED_API_KEY: API key used to retrieve publications from the NIH PubMed database
        Session Cache:
            - SCHOLAR_FLUX_CACHE_DIRECTORY: defines where requests and response processing cache will be stored when
                                             using sqlite and similar cache storages
            - SCHOLAR_FLUX_CACHE_SECRET_KEY: defines the secret key used to create encrypted session cache for request
                                             retrieval
        Logging:
            - SCHOLAR_FLUX_ENABLE_LOGGING: defines whether logging should be enabled or not
            - SCHOLAR_FLUX_LOG_DIRECTORY: defines where rotating logs will be stored when logging is enabled
            - SCHOLAR_FLUX_LOG_LEVEL: defines the default log level used for package level logging during and after
                                      scholar_flux package initialization
            - SCHOLAR_FLUX_PROPAGATE_LOGS: determines whether logs should be propagated or not. (True by default)

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
        "ARXIV_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("ARXIV_API_KEY")),
        "OPEN_ALEX_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("OPEN_ALEX_API_KEY")),
        "SPRINGER_NATURE_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("SPRINGER_NATURE_API_KEY")),
        "CROSSREF_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("CROSSREF_API_KEY")),
        "CORE_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("CORE_API_KEY")),
        "PUBMED_API_KEY": SensitiveDataMasker.mask_secret(os.getenv("PUBMED_API_KEY")),
        "SCHOLAR_FLUX_CACHE_SECRET_KEY": SensitiveDataMasker.mask_secret(os.getenv("SCHOLAR_FLUX_CACHE_SECRET_KEY")),
        "SCHOLAR_FLUX_CACHE_DIRECTORY": os.getenv("SCHOLAR_FLUX_CACHE_DIRECTORY"),
        "SCHOLAR_FLUX_LOG_DIRECTORY": os.getenv("SCHOLAR_FLUX_LOG_DIRECTORY"),
        "SCHOLAR_FLUX_MONGODB_HOST": os.getenv(
            "SCHOLAR_FLUX_MONGODB_HOST", os.getenv("MONGODB_HOST", "mongodb://127.0.0.1")
        ),
        "SCHOLAR_FLUX_MONGODB_PORT": coerce_int(os.getenv("SCHOLAR_FLUX_MONGODB_PORT", os.getenv("MONGODB_PORT")))
        or 27017,
        "SCHOLAR_FLUX_REDIS_HOST": os.getenv("SCHOLAR_FLUX_REDIS_HOST", os.getenv("REDIS_HOST", "localhost")),
        "SCHOLAR_FLUX_REDIS_PORT": coerce_int(os.getenv("SCHOLAR_FLUX_REDIS_PORT", os.getenv("REDIS_PORT"))) or 6379,
        "SCHOLAR_FLUX_ENABLE_LOGGING": os.getenv("SCHOLAR_FLUX_ENABLE_LOGGING", "").upper(),
        "SCHOLAR_FLUX_LOG_LEVEL": os.getenv("SCHOLAR_FLUX_LOG_LEVEL", "").upper(),
        "SCHOLAR_FLUX_PROPAGATE_LOGS": os.getenv("SCHOLAR_FLUX_PROPAGATE_LOGS", "").upper(),
        "SCHOLAR_FLUX_DEFAULT_PROVIDER": os.getenv("SCHOLAR_FLUX_DEFAULT_PROVIDER") or "plos",
    }

    def __init__(self, env_path: Optional[Path | str] = None):
        """Utility class for loading environment variables from the operating system and .env files."""

        self.env_path: Path = self._process_env_path(env_path)
        self.config: Dict[str, Any] = self.DEFAULT_ENV.copy()  # Use a copy to avoid modifying the class attribute

    def try_loadenv(self, env_path: Optional[Path | str] = None, verbose: bool = False) -> Optional[Dict[str, Any]]:
        """Try to load environment variables from a specified .env file into the environment and return as a dict."""
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
        """Retrieves a list of non-missing environment variables from the current .env file that are non-null.

        Args:
            env_path: Optional[Path | str]: Location of the .env file where env variables will be retrieved from
            replace_all: bool = False: Indicates whether all environment variables should be replaced vs. only non-missing variables
            verbose: bool = False: Flag indicating whether logging should be shown in the output

        Returns:
            dict: A dictionary of key-value pairs corresponding to environment variables

        """
        if env_path is not None and not isinstance(env_path, (str, Path)):
            msg = (
                f"The variable, `env_path` must be a string or path, but received a variable of {type(env_path)}. "
                "Attempting to load environment settings from default .env locations instead..."
            )
            config_logger.error(msg)
            warnings.warn(msg)
            env_path = self.env_path
        env_path = self._process_env_path(env_path or self.env_path)

        if verbose:
            config_logger.debug(f"Attempting to load environment file located at {env_path}.")

        env_config = self.try_loadenv(env_path, verbose=verbose)

        if env_config:
            config_env_variables = {
                k: self._guard_secret(v, k) for k, v in env_config.items() if replace_all or v is not None
            }
            return config_env_variables

        return {}

    @staticmethod
    def _guard_secret(
        value: Any,
        key: Optional[str] = None,
        matches: list[str] | tuple = ("API_KEY", "SECRET", "MAIL"),
    ) -> Any | SecretStr:
        """Guards the values of API keys, secrets, and likely email addresses by transforming them into secret strings.

        This static method applies masking when encountering values of type `str`. Users can optionally specify
        a `key` to apply masking when a specific keyword in `matches` matches a substring in the key.

        Args:
            value (Any): The value to convert to a string if its key contains any match
            key (Optional[str]): The value to verify if it contains any match to keys containing API_KEY/SECRET/MAIL. If
                                 key is left blank, the value will be converted into a secret string by default.
            matches (str): The substrings used to indicate whether a secret should be guarded

        Returns:
            Any | SecretStr: The original type if the value is likely not a secret. otherwise returns a SecretStr

        """
        if isinstance(value, str) and matches is not None:
            return (
                SensitiveDataMasker.mask_secret(value)
                if (key is None or re.search("|".join(matches), str(key))) and value is not None
                else value
            )
        return value

    @classmethod
    def load_os_env_key(cls, key: str, **kwargs) -> Optional[str | SecretStr]:
        """Loads the provided key from the global environment. Converts API_KEY variables to secret strings by default.

        Args:
            key (str): The key to load from the environment. This key will be guarded if it contains any of
                       the following substrings: "API_KEY", "SECRET", "MAIL"
            matches (str): The substrings used to indicate whether the loaded environment variable should be guarded

        Returns:
            Optional[str | SecretStr]: The value of the environment variable, possibly wrapped as a secret string

        """
        return cls._guard_secret(os.environ.get(key), key, **kwargs)

    def load_os_env(self, replace_all: bool = False, verbose: bool = False) -> dict:
        """Load any updated configuration settings from variables set within the system environment.

        The configuration setting must already exist in the config to be updated if available. Otherwise, the
        `update_config` method allows direct updates to the config settings.

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
        env_path: Optional[Path | str] = None,
        reload_env: bool = False,
        reload_os_env: bool = False,
        verbose: bool = False,
    ) -> None:
        """Load configuration settings from the global OS environment or an .env file while optionally overwriting
        previously set configuration settings.

        Optionally attempt to reload and overwrite previously set ConfigLoader using either or both sources
        of config settings.

        Note that config settings from an .env file are prioritized over globally set OS environment variables.
        If neither `reload_os_env` or `reload_env` are chosen, this function has no effect on the current configuration.

        Args:
            env_path (Optional[Path | str]):
                An optional env path to read from. Defaults to the current env_path if None.
            reload_env (bool):
                Determines whether environment variables will be loaded/reloaded from the provided `env_path` or a
                current `self.env_path`. Defaults to False, indicating that variables are not reloaded from an .env.
            reload_os_env (bool):
                Determines whether environment variables will be loaded/reloaded from the Operating System's global
                environment.
            verbose (bool):
                Convenience setting indicating whether or not to log changed configuration variable names.

        """

        os_config = self.load_os_env(verbose=verbose, replace_all=True) if reload_os_env else {}
        dotenv_config = self.load_dotenv(env_path, replace_all=True, verbose=verbose) if reload_env else {}

        config_env_variables = os_config | dotenv_config

        # coerce integer strings into numeric values, failing gracefully and returning the original value if impossible
        self.update_config(config_env_variables, verbose=verbose)

    def update_config(self, env_dict: dict[str, Any], verbose: bool = False) -> None:
        """Helper method for updating the config dictionary with the provided dictionary of key-value pairs.

        This method coerces strings into integers when possible and uses the `_guard_secret` method as insurance to
        guard against logging and recording API keys without masking. Although the `load_env` and `load_os_env` methods
        also mask API keys, this is particularly useful if the end-user calls `update_config` directly.

        """
        # guard sensitive environment variables when this method is used directly if not already guarded
        env_dict = {k: self._guard_secret(try_int(v), k) for k, v in env_dict.items()}

        if verbose and env_dict:
            config_logger.debug(f"Updating the following variables into the config settings: {env_dict}")

        self.config.update(env_dict)

    def save_config(self, env_path: Optional[Path | str] = None) -> None:
        """Save configuration settings to a .env file.

        Unmasks strings read as secrets if the are of the type, `SecretStr`.

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
        """Write a key-value pair to a .env file."""
        env_path = self._process_env_path(env_path or self.env_path)
        try:
            if create and not env_path.exists():
                env_path.touch()

            set_key(
                dotenv_path=str(env_path),
                key_to_set=key_name,
                value_to_set=str(SensitiveDataMasker.unmask_secret(key_value)) if key_value is not None else "",
            )
        except (IOError, PermissionError) as e:
            config_logger.error(f"Failed to create .env file at {env_path}: {e}")

    @classmethod
    def _process_env_path(cls, env_path: Optional[Union[str, Path]]) -> Path:
        """Try to load from the provided `env_path` variable first.

        Otherwise try to load from DEFAULT_ENV_PATH

        """
        if not env_path:
            return cls.DEFAULT_ENV_PATH

        raw_env_path_string = str(env_path)
        raw_env_path = Path(raw_env_path_string)
        raw_env_parent_path = raw_env_path.parent if raw_env_path_string.endswith(".env") else raw_env_path
        current_env_path = raw_env_path.resolve() if raw_env_parent_path.exists() else cls.DEFAULT_ENV_PATH
        return current_env_path / ".env" if not str(current_env_path).endswith(".env") else current_env_path


__all__ = ["ConfigLoader"]
