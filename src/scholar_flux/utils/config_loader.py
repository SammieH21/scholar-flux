import os
import logging
from dotenv import set_key, load_dotenv, dotenv_values

from pathlib import Path
from typing import Dict, Any, Optional, Union

# Initialize logger
logging.basicConfig(level=logging.INFO)
config_logger = logging.getLogger('ConfigLoader')

class ConfigLoader:
    DEFAULT_ENV_PATH: Path = Path(__file__).resolve().parent.parent / '.env'  # Default directory for the package env file

    # Values already present within the environment before loading
    DEFAULT_ENV: Dict[str, Any] = {
        'SPRINGER_API_KEY': os.getenv('SPRINGER_API_KEY'),
        'CROSSREF_API_KEY': os.getenv('CROSSREF_API_KEY'),
        'CORE_API_KEY': os.getenv('CORE_API_KEY'),
        'CACHE_SECRET_KEY': os.getenv('CACHE_SECRET_KEY'),
        'LOG_DIRECTORY': os.getenv('SCHOLAR_FLUX_LOG_DIR') or None,
        'LOG_LEVEL': os.getenv('SCHOLAR_FLUX_LOG_LEVEL') or 'DEBUG',
        'DEFAULT_SCHOLAR_FLUX_PROVIDER': os.getenv('DEFAULT_SCHOLAR_FLUX_PROVIDER') or 'plos'
    }

    def __init__(self, env_path: Optional[Path | str] = None):
        """Utility class for loading environment variables from a .env file"""

        self.env_path: Path = self._process_env_path(env_path)
        self.config: Dict[str, Any] = self.DEFAULT_ENV.copy()  # Use a copy to avoid modifying the class attribute

    def try_loadenv(self, env_path: Optional[Path | str]=None, verbose: bool = False) -> Optional[Dict[str, Any]]:
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

    def load_config(self, reload_env: bool = False, env_path: Optional[Path | str] = None, verbose: bool= False) -> None:
        """
        Load configuration settings from a .env file.
        """
        if reload_env:
            env_path = self._process_env_path(env_path or self.env_path)
            if verbose:
                config_logger.debug(f"Attempting to load environment file located at {env_path}.")
            env_config = self.try_loadenv(env_path, verbose=False)
            if env_config:
                self.config.update({k: v for k, v in env_config.items() if v is not None})

    def save_config(self, env_path: Optional[Path | str] = None) -> None:
        """
        Save configuration settings to a .env file.
        """
        env_path = env_path or self.env_path
        for key, value in self.config.items():
            if value is not None:
                self.write_key(key, value, env_path)

    def write_key(self, key_name: str, key_value: str, env_path: Optional[Path | str] = None, create: bool = True) -> None:
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

# Example usage
if __name__ == "__main__":
    config_loader = ConfigLoader()
    config_loader.load_config(reload_env=True)
    config_loader.save_config()

