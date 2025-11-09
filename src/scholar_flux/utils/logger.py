# utils/logger.py
"""The scholar_flux.utils.logger module implements a basic logger used to create an easy-to-re-initialize logger to be
used for logging events and progress in the retrieval and processing of API responses."""
import logging
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

# for creating a function that masks URLs containing API keys:
from scholar_flux.package_metadata import get_default_writable_directory
from scholar_flux.exceptions import LogDirectoryError


def setup_logging(
    logger: Optional[logging.Logger] = None,
    log_directory: Optional[str] = None,
    log_file: Optional[str] = "application.log",
    log_level: int = logging.DEBUG,
    propagate_logs: Optional[bool] = True,
    max_bytes: int = 1048576,
    backup_count: int = 5,
    logging_filter: Optional[logging.Filter] = None,
):
    """Configure logging to write to both console and file with optional filtering.

    Sets up a logger that outputs to both the terminal (console) and a rotating log file.
    Rotating files automatically create new files when size limits are reached, keeping
    your logs manageable.

    Args:
        logger (Optional[logging.Logger]): The logger instance to configure. If None, uses the root logger.
        log_directory (Optional[str]): Indicates where to save log files. If None, automatically finds a writable
                                       directory when a log_file is specified..
        log_file (Optional[str]): Name of the log file (default: 'application.log'). If None, file-based logging
                                  will not be performed.
        log_level (int): Minimum level to log (DEBUG logs everything, INFO skips debug messages).
        propagate_logs (Optional[bool]): Determines whether to propagate logs. Logs are propagated by default if this
                                         option is not specified.
        max_bytes (int): Maximum size of each log file before rotating (default: 1MB).
        backup_count (int): Number of old log files to keep (default: 5).
        logging_filter (Optional[logging.Filter]): Optional filter to modify log messages (e.g., hide sensitive data).

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

    # Create or get a root logger if it doesn't yet exist
    if not logger:
        logger = logging.getLogger(__name__)

    logger.setLevel(log_level)

    # Construct the full path for the log file
    try:
        # Attempt to create the log directory within the package
        if log_file:
            current_log_directory = (
                Path(log_directory) if log_directory is not None else get_default_writable_directory("logs")
            )
            logger.info("Using the current directory for logging: %s", current_log_directory)
        else:
            current_log_directory = None

    except RuntimeError as e:
        logger.error("Could not identify or create a log directory due to an error: %s", e)
        raise LogDirectoryError(f"Could not identify or create a log directory due to an error: {e}.")

    # Clear existing handlers (useful if setup_logging is called multiple times)
    logger.handlers = []

    # Propagate logs by default. `bool()` is used to explicitly map truthy or falsy values to True/False
    logger.propagate = True if propagate_logs is None else bool(propagate_logs)

    # Define a formatter for both console and file logging
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # create a handler for console logging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # create a handler for file logs
    log_file_path = current_log_directory / log_file if current_log_directory and log_file else None

    if log_file_path:
        file_handler = RotatingFileHandler(str(log_file_path), maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setFormatter(formatter)
    else:
        file_handler = None

    # add both file and console handlers to the logger
    if logging_filter:
        # Add a sensitive data masking filter to both file and console handlers
        console_handler.addFilter(logging_filter)
    logger.addHandler(console_handler)

    if file_handler:
        if logging_filter:
            file_handler.addFilter(logging_filter)
        logger.addHandler(file_handler)

    # indicate the location where logs are created, if created
    logging_type = f"(folder: {log_file_path})" if log_file_path else "(console_only)"
    logger.info("Logging setup complete %s", logging_type)


__all__ = ["setup_logging"]
