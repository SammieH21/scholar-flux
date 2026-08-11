# utils/logger.py
"""The scholar_flux.utils.logger module implements a basic logger used to create an easy-to-re-initialize logger to be
used for logging events and progress in the retrieval and processing of API responses."""

import logging
from pathlib import Path
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from sys import stdout, stderr
from typing import TextIO, Literal

# for creating a function that masks URLs containing API keys:
from scholar_flux.package_metadata import get_default_writable_directory
from scholar_flux.exceptions import LogDirectoryError
from scholar_flux.utils.helpers import coerce_int, coerce_bool
from contextlib import contextmanager
import re
import warnings


def setup_logging(
    logger: logging.Logger | None = None,
    log_directory: str | None = None,
    log_file: str | None = "application.log",
    log_level: int = logging.DEBUG,
    propagate_logs: bool | None = True,
    max_bytes: int = 1048576,
    backup_count: int = 5,
    logging_filter: logging.Filter | None = None,
    *,
    stream: TextIO | Literal[False] | None = None,
    raise_on_error: bool = True,
) -> None:
    """Configures a logger to write to the console and, optionally, file logs with an optional logging filter.

    This function is a general purpose utility used by the `scholar_flux` package to set up a package level logger that
    implements sensitive data masking with a custom filter.

    The logger is configured to write to the terminal (console) and, if optionally a rotating log file. if specified.
    Rotating files automatically create new files when size limits are reached, keeping your logs manageable.

    Args:
        logger (Optional[logging.Logger]): The logger instance to configure. If None, uses the root logger.
        log_directory (Optional[str]): Indicates where to save log files. If None, automatically finds a writable
                                       directory when a log_file is specified.
        log_file (Optional[str]): Name of the log file (default: 'application.log'). If None, file-based logging
                                  will not be performed.
        log_level (int): Minimum level to log (DEBUG logs everything, INFO skips debug messages).
        propagate_logs (Optional[bool]): Determines whether to propagate logs. Logs are propagated by default if this
                                         option is not specified.
        max_bytes (int): Maximum size of each log file before rotating (default: 1MB).
        backup_count (int): Number of old log files to keep (default: 5).
        logging_filter (Optional[logging.Filter]): Optional filter to modify log messages (e.g., hide sensitive data).
        stream (Optional[TextIO | bool]):
            Optionally modifies the stream used for logging. By default, a stream is created that uses `stderr`.
            Set this to False to avoid creating a log stream altogether.
        raise_on_error (bool):
            Indicates whether an error should be raised if an error occurs during file-based logging setup.

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
            current_log_directory: Path | None = (
                Path(log_directory).expanduser()
                if log_directory is not None
                else get_default_writable_directory("logs")
            )
            logger.info("Using the current directory for logging: %s", current_log_directory)
        else:
            current_log_directory = None

    except RuntimeError as e:
        err = f"Could not identify or create a log directory due to an error: {e}"

        if raise_on_error:
            raise LogDirectoryError(err)

        warnings.warn(f"{err}. Disabling File-based logging...", stacklevel=2)
        current_log_directory = None

    # Clear existing handlers (useful if setup_logging is called multiple times)
    logger.handlers = []

    # Propagate `bool()` is used to explicitly map truthy or falsy values to True/False
    logger.propagate = bool(propagate_logs)

    # Define a formatter for both console and file logging
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # create a handler for console logging
    console_handler = logging.NullHandler() if stream is False else logging.StreamHandler(stream)
    console_handler.setFormatter(formatter)

    # add both file and console handlers to the logger. No-Op when streaming is not enabled
    if logging_filter:
        # Add a sensitive data masking filter to both file and console handlers
        console_handler.addFilter(logging_filter)

    logger.addHandler(console_handler)

    file_handler: RotatingFileHandler | None = None

    # create a handler for file logs
    log_file_path = current_log_directory / log_file if current_log_directory and log_file else None

    if log_file_path:
        try:
            file_handler = RotatingFileHandler(str(log_file_path), maxBytes=max_bytes, backupCount=backup_count)
            file_handler.setFormatter(formatter)

            if logging_filter:
                file_handler.addFilter(logging_filter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError) as e:
            err = f"Encountered an error setting up the rotating file handler: {e}"
            if raise_on_error:
                raise LogDirectoryError(err) from e
            warnings.warn(f"{err}\nDisabling file-based logging...", stacklevel=2)

    # indicate the location where logs are created, if created
    logging_type = f"(folder: {log_file_path})" if file_handler else "(console_only)"
    logger.info("Logging setup complete %s", logging_type)


@contextmanager
def log_level_context(
    log_level: int | str = logging.DEBUG, logger: logging.Logger | None = None, allow_lower_level: bool = True
) -> Iterator[None]:
    """Context manager for temporarily changing the log level for the package-level (or custom) logger.

    Args:
        log_level (int | str):
            The log level to temporarily change to. Options include:
            - logging.DEBUG (10) or "DEBUG"
            - logging.INFO (20) or "INFO"
            - logging.WARNING (30) or "WARNING"
            - logging.ERROR (40) or "ERROR"
            - logging.CRITICAL (50) or "CRITICAL"
        logger (logging.Logger):
            The logger to use when temporarily changing the log level. If not specified, the `ScholarFlux` package level
            logger is used.
        allow_lower_level (bool):
            When False, The current log level is overridden only when the provided log level is higher than the current
            log level.

    Example:
        >>> from scholar_flux import SearchAPI, log_level_context
        >>> api = SearchAPI(provider_name = "CORE", query = "Technological Safety")
        >>> with log_level_context("DEBUG"): # `logging.DEBUG`
        ...     response = api.search(page = 1)
        # OUTPUT: 2026-01-21 13:46:50,333 - scholar_flux.api.base_api - DEBUG - Sending request to https://api.core.ac.uk/v3/search/works

    Note: when an invalid log_level is passed, a level of `51` is used in its place, effectively turning off logging.

    """
    # Turns off logging altogether if an invalid value is passed (e.g., passing `log_level='not a valid log level'`)
    level = log_level if isinstance(log_level, int) else getattr(logging, log_level, 51)
    target_logger = logger if logger else logging.getLogger("scholar_flux")
    current_level = target_logger.level

    try:
        if isinstance(level, int) and (allow_lower_level or level > current_level):
            target_logger.setLevel(level)
        yield
    finally:
        target_logger.setLevel(current_level)


def resolve_log_stream(stream: str | bool | TextIO | None) -> TextIO | Literal[False]:
    """Helper for resolving streams used for logging from strings.

    Args:
        stream (Optional[str | bool | TextIO]):
            The value to resolve as a stream type.

    Returns:
        TextIO: A `stderr` or `stdout` stream resolved from the input.
        Literal[False]: If `False` or a similar, falsy value is received (eg., 0, '0', 'false')

    Note:
        This function attempts to resolve values into `stderr` or `stdout` using case-insensitive string normalization
        when possible. A value of `False`, when returned, indicates that streaming should not be used. If a value
        other than a string is passed (e.g., None, True, 23), the stream will default to `stderr` instead.

    """

    # Format and clean strings when applicable - otherwise resolve as None
    stream_fmt = re.sub("[^a-z]", "", stream.lower()) if isinstance(stream, str) else stream

    if coerce_bool(stream_fmt) is False:
        return False

    # Return either stderr or stdout
    return stdout if stream_fmt in ("stdout", stdout) else stderr


def resolve_log_level(log_level: str | int | None = None) -> int | None:
    """Utility for resolving numeric strings and log level values into integer log levels.

    Args:
        log_level (Optional[str | int]):
            The log level to resolve as an integer if not already an integer. Accepts both case-insensitive strings
            ("Warning", "INFO", "error") and integers ("0", 1, "03")

    Returns:
        int: The logging level that is either resolved from the user-provided `log_level`
        None: When non-string/non-integer is received or log level resolution from a string is unsuccessful

    """

    if isinstance(log_level, int):
        return log_level

    if not isinstance(log_level, str):
        return None

    log_level_string = log_level.strip()

    return (
        coerce_int(log_level_string)
        if log_level_string.isnumeric()
        else getattr(logging, log_level_string.upper(), None)
    )


__all__ = ["setup_logging", "log_level_context", "resolve_log_stream", "resolve_log_level"]
