# utils/logger.py
import logging
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

# for creating a function that masks URLs containing API keys:
from scholar_flux.package_metadata import get_default_writable_directory
from scholar_flux.exceptions import LogDirectoryError

# def mask_field(arg: str) -> str:
#     """
#     Used to mask sensitive fields in strings before they show in logs
#     The following fields are masked when identified:
#         1. api keys
#         2. emails
#         3. authentication bearer tokens
#
#     Args:
#         arg (str): A string that may or may not contain fields that we wish
#                    to mask
#     Returns:
#         (str): The same string that masks any identified sensitive fields that
#                 we would like to exclude from logs
#     """
#     # Assuming 'api_key' is the query parameter for the API key
#     api_key_fields = ['api_key', 'apikey','API_KEY','APIKEY']
#
#     # ensure that various forms of the API key parameter are masked
#     api_key_regex = r"([A-Za-z0-9\-_]+)"
#     for key in api_key_fields:
#         arg = re.sub(fr"{key} ?(\:|\=) ?'?{api_key_regex}'?", f'{key}=***', arg)
#
#     email_fields = ['mail', 'mailto']
#
#     # ensure that various forms of the API key parameter are masked
#     email_regex = fr'[a-zA-Z0-9._%+-]+(%40|@)[a-zA-Z0-9.-]+\.[a-zA-Z]+(\.[a-zA-Z]+)?'
#     for key in email_fields:
#         arg = re.sub(fr"{key} ?(\:|\=) ?'?{email_regex}'?", f'{key}=***', arg)
#
#     bearer_regex = r"[Aa]uthorization [Bb]earer\:? *"
#     arg = re.sub(fr"({bearer_regex}){api_key_regex}", "\\1***", arg)
#     return arg
#
# ## create a class that applies the filter:class MaskAPIKeyFilter(logging.Filter):
# # Define a custom logging filter to mask API keys in log messages
# class MaskAPIKeyFilter(logging.Filter):
#     """This class is a utility API mask to prevent API keys from showing in logs"""
#     def filter(self, record: Any):
#         if record.args:
#             record.args = tuple(mask_field(arg) if isinstance(arg, str) else arg for arg in record.args)
#
#         if isinstance(record.msg, str):
#             record.msg = mask_field(record.msg)
#         return True


def setup_logging(
    logger: Optional[logging.Logger] = None,
    log_directory: Optional[str] = None,
    log_file: str = "application.log",
    log_level: int = logging.DEBUG,
    max_bytes: int = 1048576,
    backup_count: int = 5,
    logging_filter: Optional[logging.Filter] = None,
):
    """
    Configure logging to write to both console and file with optional filtering.

    Sets up a logger that outputs to both the terminal (console) and a rotating log file.
    Rotating files automatically create new files when size limits are reached, keeping
    your logs manageable.

    Args:
        logger: The logger instance to configure. If None, uses the root logger.
        log_directory: Where to save log files. If None, automatically finds a writable directory.
        log_file: Name of the log file (default: 'application.log').
        log_level: Minimum level to log (DEBUG logs everything, INFO skips debug messages).
        max_bytes: Maximum size of each log file before rotating (default: 1MB).
        backup_count: Number of old log files to keep (default: 5).
        logging_filter: Optional filter to modify log messages (e.g., hide sensitive data).

    Example:
        >>> # Basic setup - logs to console and file
        >>> setup_logging()

        >>> # Custom location and less verbose
        >>> setup_logging(log_directory="/var/log/myapp", log_level=logging.INFO)

        >>> # With sensitive data masking
        >>> from scholar_flux.security import MaskingFilter
        >>> mask_filter = MaskingFilter()
        >>> setup_logging(logging_filter=mask_filter)

    Note:
        - Console shows all log messages in real-time
        - File keeps a permanent record with automatic rotation
        - If logging_filter is provided, it's applied to both console and file output
        - Calling this function multiple times will reset the logger configuration
    """

    # Create a root logger if it doesn't yet exist
    if not logger:
        logger = logging.getLogger()

    logger.setLevel(log_level)

    # Construct the full path for the log file
    try:
        # Attempt to create the log directory within the package
        current_log_directory = (
            Path(log_directory)
            if log_directory is not None
            else get_default_writable_directory("logs")
        )
        logger.info(
            "Using the current directory for logging: %s", current_log_directory
        )
    except RuntimeError as e:
        logger.error("Failed to identify a directory for logging: %s", e)
        raise LogDirectoryError(
            f"Could not identify or create a log directory due to an error: {e}."
        )

    log_file_path = current_log_directory / log_file

    # Clear existing handlers (useful if setup_logging is called multiple times)
    logger.handlers = []

    # Define a formatter for both console and file logging
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s"
    )

    # create a handler for console logging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # create a handler for file logs
    file_handler = RotatingFileHandler(
        str(log_file_path), maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setFormatter(formatter)

    if logging_filter:
        # Add a sensitive data masking filter to both file and console handlers
        console_handler.addFilter(logging_filter)
        file_handler.addFilter(logging_filter)

    # add both file and console handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("Logging setup complete (folder: %s)", log_file_path)
