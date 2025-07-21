import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union, Any
import os
import re
from logging.handlers import RotatingFileHandler

# for creating a function that masks URLs containing API keys:
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def mask_api_key(arg: str) -> str:
    """Used to mask api keys in strings before they show in logs"""
    # Assuming 'api_key' is the query parameter for the API key
    api_key_fields = ['api_key', 'apikey','API_KEY','APIKEY']

    # ensure that various forms of the API key parameter are masked
    for key in api_key_fields:
        arg = re.sub(fr"{key} ?= ?'?([A-Za-z0-9\-_]+)'?", f'{key}=***', arg)
    return arg


## create a class that applies the filter:class MaskAPIKeyFilter(logging.Filter):
# Define a custom logging filter to mask API keys in log messages
class MaskAPIKeyFilter(logging.Filter):
    """This class is a utility API mask to prevent API keys from showing in logs"""
    def filter(self, record: Any):
        if record.args:
            record.args = tuple(mask_api_key(arg) if isinstance(arg, str) else arg for arg in record.args)

        if isinstance(record.msg, str):
            record.msg = mask_api_key(record.msg)
        return True


def setup_logging(logger: Optional[logging.Logger] = None,
                  log_directory: Optional[str] = None,
                  log_file: str ='application.log',
                  log_level: int = logging.DEBUG,
                  max_bytes: int = 1048576,
                  backup_count: int =5):
    """
    Sets up the logging configuration for the application.
    """
    # Create the logs directory if it does not exist
    #log_directory = os.path.abspath(log_directory)

    #os.makedirs(log_directory, exist_ok=True)

    # Create a root logger
    if not logger:
        logger = logging.getLogger()


    # Construct the full path for the log file
    try:
        # Attempt to create the log directory within the package
        current_log_directory = Path(log_directory) if log_directory is not None else Path(__file__).resolve().parent.parent / 'logs'
        current_log_directory.mkdir(parents=True, exist_ok=True)

    except PermissionError:
        # Fallback to a directory in the user's home folder
        try:
            current_log_directory = Path.home() / '.scholarly_explorer' / 'logs'
            current_log_directory.mkdir(parents=True, exist_ok=True)
            logger.info("Using home directory for Logs: %s", current_log_directory)
        except PermissionError as e:
            logger.error("Failed to create log directory in home: %s", e)
            # Handle further or raise an exception to inform the user
            raise ValueError("Could not create log directory due to permission issues.")
    log_file_path= current_log_directory / log_file

    # Clear existing handlers (useful if setup_logging is called multiple times)
    logger.handlers = []

    # Define a formatter for the log messages
    logger.setLevel(log_level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Add the mask API key filter to the logger
    mask_filter = MaskAPIKeyFilter()
    handler.addFilter(mask_filter)
    logger.addHandler(handler)

    # Setup file logging with log rotation
    file_handler = RotatingFileHandler(str(log_file_path), maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logging setup complete (folder: %s)",log_file_path)

