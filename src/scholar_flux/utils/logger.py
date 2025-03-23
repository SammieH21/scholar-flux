import logging
from pathlib import Path
import os
import re
from logging.handlers import RotatingFileHandler


### for creating a function that masks URLs containing API keys:

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def mask_api_key_in_url(url: str) -> str:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    # Assuming 'api_key' is the query parameter for the API key
    if 'api_key' in query_params:
        query_params['api_key'] = ['*MASKED*']
    
    # Reconstruct the URL with the masked query parameters
    new_query = urlencode(query_params, doseq=True)
    masked_url = urlunparse(parsed_url._replace(query=new_query))
    
    return masked_url

## create a class that applies the filter:class MaskAPIKeyFilter(logging.Filter):
# Define a custom logging filter to mask API keys in log messages
class MaskAPIKeyFilter(logging.Filter):
    def filter(self, record):
        if record.args:
            record.args = tuple(re.sub(r'api_key=([A-Za-z0-9\-_]+)', 'api_key=***', arg) if isinstance(arg, str) else arg for arg in record.args)
        if isinstance(record.msg, str):
            record.msg = re.sub(r'api_key=([A-Za-z0-9\-_]+)', 'api_key=***', record.msg)
        return True


def setup_logging(log_directory=None, log_file='application.log',
                log_level=logging.DEBUG, max_bytes=1048576, backup_count=5):
    """
    Sets up the logging configuration for the application.

    Args:
        log_directory (str): Directory where log files will be stored.
        log_file (str): Name of the log file.
        log_level (int): The minimum logging level messages to capture.
        max_bytes (int): Maximum size in bytes before rotating the log file.
        backup_count (int): Number of backup files to keep.
    """
    # Create the logs directory if it does not exist
    #log_directory = os.path.abspath(log_directory)

    #os.makedirs(log_directory, exist_ok=True)
    
    

    # Construct the full path for the log file
    try:
        # Attempt to create the log directory within the package
        log_directory = Path(log_directory) if log_directory is not None else Path(__file__).resolve().parent.parent / 'logs'
        log_directory.mkdir(parents=True, exist_ok=True)
    
    except PermissionError:
        # Fallback to a directory in the user's home folder
        try:
            log_directory = Path.home() / '.scholarly_explorer' / 'logs'
            log_directory.mkdir(parents=True, exist_ok=True)
            logger.info("Using home directory for Logs: %s", log_file_path)
        except PermissionError as e:
            logger.error("Failed to create log directory in home: %s", e)
            # Handle further or raise an exception to inform the user
            raise ValueError("Could not create log directory due to permission issues.")
    log_file_path= log_directory / log_file


    # Define a formatter for the log messages
    

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # Add the mask API key filter to the logger
    mask_filter = MaskAPIKeyFilter()
    logger.addFilter(mask_filter)
    
    
    # Clear existing handlers (useful if setup_logging is called multiple times)
    logger.handlers = []

    # Setup console logging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    

    # Setup file logging with log rotation
    file_handler = RotatingFileHandler(str(log_file_path), maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # class MaskAPIKeyHandler(logging.StreamHandler):
    #     def emit(self, record):
    #         if record.msg and 'api_key=' in record.msg:
    #             record.msg = re.sub(r'api_key=[A-Za-z0-9\-_]+', 'api_key=***', record.msg)
    #         super().emit(record)
    #urllogger = logging.getLogger("urllib3")
    #urllogger.handlers = []
    #urllogger.addFilter(MaskAPIKeyFilter())
    #urllogger.addHandler(MaskAPIKeyHandler())
    
    logger.info("Logging setup complete. %s",log_file_path)
# class MaskAPIKeyFilter(logging.Filter):
#     def filter(self, record):
#         if record.args:
#             record.args = tuple(re.sub(r'api_key=([A-Za-z0-9\-_]+)', 'api_key=***', arg) if isinstance(arg, str) else arg for arg in record.args)
#         if isinstance(record.msg, str):
#             record.msg = re.sub(r'api_key=([A-Za-z0-9\-_]+)', 'api_key=***', record.msg)
#         return True