from scholar_flux.utils.logger import setup_logging, resolve_log_stream, resolve_log_level
from scholar_flux.exceptions import LogDirectoryError, PackageInitializationError
from scholar_flux import initialize_package
from unittest.mock import MagicMock
from scholar_flux.utils import ConfigLoader, config_settings
from tests.testing_utilities import raise_error
from pydantic import SecretStr
import logging
import pytest
from scholar_flux import log_level_context
from scholar_flux import logger
from sys import stdout, stderr, stdin


def test_initialization_env_path_fallback(restore_config_settings, recwarn, caplog):
    """Verifies that initialization records a warning and uses defaults when an env_path is of an incorrect type."""
    env_path = 10021
    updated_config, _, _ = initialize_package(env_path=env_path)  # type: ignore
    assert restore_config_settings == updated_config
    msg = (
        f"The variable, `env_path` must be a string or path, but received a variable of {type(env_path)}. "
        "Attempting to load environment settings from default .env locations instead..."
    )
    assert msg in caplog.text
    warning_message = str(recwarn[0].message)
    assert msg in warning_message


def test_initialization_invalid_dictionary_parameters():
    """Verifies that a PackageInitializationError error is raised when invalid parameters are used on initialization."""
    base_error = "An error occurred in the reinitialization of scholar_flux: "
    not_a_dictionary = ["1", "2", "3"]
    with pytest.raises(PackageInitializationError) as excinfo:
        _ = initialize_package(config_params=not_a_dictionary)  # type: ignore
    assert f"{base_error}`config_params` must be a dictionary, but received type {type(not_a_dictionary)}." in str(
        excinfo.value
    )

    with pytest.raises(PackageInitializationError) as excinfo:
        _ = initialize_package(logging_params=not_a_dictionary)  # type: ignore
    assert f"{base_error}`logging_params` must be a dictionary, but received type {type(not_a_dictionary)}." in str(
        excinfo.value
    )


def test_logging_setup_with_directory(tmp_path, cleanup, caplog):
    """Tests whether a log file can be successfully set up in a temp directory."""
    log_file = "application.log"
    logger = logging.getLogger("test_logger")

    setup_logging(logger, log_file=log_file, log_directory=tmp_path, log_level=logging.INFO)
    assert f"Logging setup complete (folder: {tmp_path}/{log_file})" in caplog.text
    assert logger.level == logging.INFO


def test_logging_setup_without_directory(caplog):
    """Tests whether a logger can be successfully set up without rotary file logging (console logging only)."""
    setup_logging(log_file=None)
    assert "Logging setup complete (console_only)" in caplog.text


@pytest.mark.parametrize(
    "env_log_level,should_warn,resolved,expected",
    (
        (logging.DEBUG, False, logging.DEBUG, logging.DEBUG),
        (0, False, 0, 0),
        (45, False, 45, 45),
        ("", False, None, logging.WARNING),
        ([1, 2, 3], True, None, logging.WARNING),
        ("None", False, None, logging.WARNING),
        ("Unknown Log Level", True, None, logging.WARNING),
        ("DEBUG", False, logging.DEBUG, logging.DEBUG),
        ("info", False, logging.INFO, logging.INFO),
    ),
)
def test_log_level_resolved_from_env(env_log_level, should_warn, resolved, expected, restore_config_settings, caplog):
    """Tests whether `initialize_package` gracefully handles log level resolution from the environment when possible."""
    assert resolve_log_level(env_log_level) == resolved  # Either resolves correctly or returns None

    logger = logging.getLogger("test_logger")
    config_settings.set("SCHOLAR_FLUX_LOG_LEVEL", env_log_level)
    _ = initialize_package(logging_params=dict(logger=logger))
    assert logger.level == expected
    warned = f"'{env_log_level}' is not a valid log level. defaulted to log level WARNING instead." in caplog.text
    assert warned ^ (not should_warn)


@pytest.mark.parametrize(
    "stream,expected",
    (
        (stdout, stdout),  # The default
        (stderr, stderr),  # Allow for a little grace
        (None, stderr),  # The default
        ("STDERR", stderr),
        ("STDOUT", stdout),  # STDOUT should be resolvable despite caps
        ("STD Out", stdout),  # Allow for a little grace
        ("stdout", stdout),
        (True, stderr),
        ("Incorrect stream value", stderr),  # default to stderr when invalid
        (stdin, stderr),  # Not quite the expected value for a logger
        (False, False),  # Turns off logging
        ("False", False),  # Also turns off logging after resolving "False" to `False`
        ("FALSE", False),  # Case insensitive
    ),
)
def test_log_stream_resolution(stream, expected, restore_config_settings, caplog):
    """Tests whether `resolve_log_stream` gracefully handles stream resolution when possible."""
    assert resolve_log_stream(stream) == expected

    logger = logging.getLogger("test_logger")
    config_settings.set("SCHOLAR_FLUX_LOG_STREAM", stream)
    initialize_package(logging_params=dict(logger=logger))
    logger_stream = getattr(logger.handlers[0], "stream", None)
    assert (expected is False and isinstance(logger.handlers[0], logging.NullHandler)) or logger_stream == expected


def test_initializer_logger_creation_without_modification(caplog):
    """Tests whether the initializer can create a new logger without modifying the original "scholar_flux" logger.

    The `scholar_flux` logger is a package level logger that can be retrieved using
    `logger = logging.getLogger("scholar_flux")` and is set at the level of `DEBUG` at the beginning of the test suite.

    The `initialize_package` function is used to set up logging and masking based on the config set with environment
    variables and optional direct overrides. `new-logger` should not modify the original `scholar_flux` logger.

    """

    logger = logging.getLogger("scholar_flux")
    new_logger = logging.getLogger("new-logger")

    # setting up a new logger with the log level - ERROR (this shouldn't modify the original `scholar_flux` logger)
    _ = initialize_package(logging_params=dict(logger=new_logger, log_level=logging.WARNING))

    assert new_logger.level == logging.WARNING
    assert logger.level == logging.DEBUG

    message = "This message should show in the logs"
    new_message = "This message shouldn't show in the logs"

    # tests ran with the `scholar_flux` should be displayed under the DEBUG logging level as usual
    logger.debug(message)

    # the new logger only logs at the `WARNING` level, so this shouldn't show in caplog
    new_logger.debug(new_message)

    assert new_message not in caplog.text
    assert message in caplog.text


def test_logging_context_with_new_logger(caplog):
    """Tests whether the log level for package level loggers can be successfully overridden via `log_level_context`."""
    test_logger = logging.getLogger("context-logger-testing")
    initialize_package(log=False, logging_params=dict(logger=test_logger, log_level=logging.WARNING))

    message = "this message should show in the log"
    with log_level_context(logging.DEBUG, test_logger):
        test_logger.debug(message)
        assert message in caplog.text

    # critical log levels only
    message = "this message should NOT show in the log"
    with log_level_context(log_level=logging.CRITICAL, logger=test_logger):
        test_logger.error(message)
        assert message not in caplog.text


def test_package_level_logging_context(caplog):
    """Verifies that the `log_level_context` modifies the log level for the package logger as intended when set."""
    message = "Does this show in the logs?"
    with log_level_context(logging.CRITICAL):
        logger.warning(message)
        assert message not in caplog.text
        with log_level_context(logging.DEBUG):
            logger.info(message)
            assert message in caplog.text
        caplog.clear()
        with log_level_context(logging.DEBUG, allow_lower_level=False):
            logger.info(message)
            assert message not in caplog.text


def test_initializer_without_logging(caplog):
    """Tests whether the initializer correctly ensures that logging does not occur with log = False on setup."""
    test_logger = logging.getLogger("null-logger-testing")
    initialize_package(log=False, logging_params=dict(logger=test_logger, log_level=logging.DEBUG))
    message = "this message shouldn't show in the log"
    test_logger.debug(message)
    assert message not in caplog.text


def test_initializer_with_env(restore_config_settings, cleanup, tmp_path, monkeypatch, caplog):
    """Tests whether the initializer can effectively use `.env` files to load config/logger environment variables."""
    test_logger = logging.getLogger("env-logger-testing")
    env_path = tmp_path / ".env"

    provider = "arXiv"
    crossref_api_key_env_var = "CROSSREF_API_KEY"
    mocked_crossref_api_key = "COMPLETELY_FAKE_API_KEY1234"

    with open(env_path, "w") as f:
        f.writelines("SCHOLAR_FLUX_LOG_LEVEL=ERROR\n")
        f.writelines(f"SCHOLAR_FLUX_DEFAULT_PROVIDER={provider}")

    with monkeypatch.context() as m:
        m.setenv(crossref_api_key_env_var, mocked_crossref_api_key)

        config, _, _ = initialize_package(
            env_path=env_path, config_params=dict(reload_os_env=True), logging_params=dict(logger=test_logger)
        )

        assert test_logger.level == logging.ERROR
        assert config_settings.get("SCHOLAR_FLUX_DEFAULT_PROVIDER") == provider
        assert "Attempting to load updated settings from the system environment." in caplog.text
        assert SecretStr(mocked_crossref_api_key) == config.get(crossref_api_key_env_var)
        assert mocked_crossref_api_key not in caplog.text


def test_config_with_missing_env(cleanup, tmp_path, caplog):
    """Tests that failed attempts to load configurations will pass gracefully and log when the env file is missing."""
    original_config = config_settings.config.copy()
    test_logger = logging.getLogger("env-logger-testing")
    env_path = tmp_path / ".env"

    config, _, _ = initialize_package(env_path=env_path, logging_params=dict(logger=test_logger))

    assert config == original_config

    assert f"No environment file located at {env_path}" in caplog.text


def test_initializer_propagation(caplog):
    """Tests whether the initializer correctly specifies log message propagation consistently via `propagate_logs`."""
    test_logger = logging.getLogger("test-logger-propagation")
    initialize_package(logging_params=dict(logger=test_logger, log_level=logging.DEBUG))
    assert test_logger.propagate is True
    message = "test log message propagation"
    test_logger.debug(message)
    assert message in caplog.text
    caplog.clear()
    initialize_package(logging_params=dict(logger=test_logger, propagate_logs=False))
    assert test_logger.propagate is False
    assert message not in caplog.text


def test_setup_logging_value_error(monkeypatch):
    """Tests whether the initializer raises a PackageInitializationError when logging setup fails."""
    test_logger = logging.getLogger("test-logger-propagation")
    err = "Could not locate a writable logs directory for scholar_flux"
    monkeypatch.setattr("scholar_flux.utils.logger.get_default_writable_directory", raise_error(RuntimeError, err))

    with pytest.raises(PackageInitializationError) as excinfo:
        _ = initialize_package(logging_params=dict(logger=test_logger, log_level=logging.ERROR, raise_on_error=True))

    msg = (
        "Failed to initialize the logger for the scholar_flux package: Could not identify or create a log directory "
        f"due to an error: {err}"
    )
    assert msg in str(excinfo.value)


def test_setup_logging_directory_exception_warning(monkeypatch, recwarn):
    """Tests whether the initializer gracefully warns when a directory selection issue is encountered during log setup.

    When `raise_on_error=False`, this method should forego raising a `PackageInitializationError` and should instead use
    the `warnings` library to indicate an issue during directory setup.

    """
    test_logger = logging.getLogger("test-logger-propagation")
    err = "Could not locate a writable logs directory for scholar_flux"
    monkeypatch.setattr("scholar_flux.utils.logger.get_default_writable_directory", raise_error(RuntimeError, err))

    _, logger, _ = initialize_package(logging_params=dict(logger=test_logger, log_level=logging.ERROR))
    assert logger.handlers and len(logger.handlers) == 1  # Should only include the console handler at this point

    assert (
        "Could not identify or create a log directory " f"due to an error: {err}. Disabling File-based logging..."
    ) in str(recwarn[0].message)


def test_configuration_loading_fallback(monkeypatch, recwarn):
    """Verifies that the initializer falls back to default config settings and warns users for config loading errors."""
    test_logger = logging.getLogger("test-logger-propagation")
    err = "Could not load package configuration settings"
    monkeypatch.setattr(
        "scholar_flux.utils.config_loader.ConfigLoader.load_config",
        raise_error(RuntimeError, err),
    )
    config, returned_logger, _ = initialize_package(logging_params=dict(logger=test_logger, log_level=logging.ERROR))

    assert test_logger is returned_logger

    # Check only items that can be found within the config loader
    assert {k: v for k, v in config.items() if k in ConfigLoader.DEFAULT_ENV} == ConfigLoader.DEFAULT_ENV
    assert test_logger.level == logging.ERROR
    warning_message = str(recwarn[0].message)
    assert (
        "Failed to load the configuration settings for the scholar_flux package. Falling back to the default "
        f"configuration settings: {err}" in warning_message
    )


def test_logging_directory_setup_failure(monkeypatch):
    """Tests whether unsuccessfully setting up a logger will raise the required exception."""
    log_file = "app.log"
    monkeypatch.setattr(
        "scholar_flux.utils.logger.get_default_writable_directory", MagicMock(side_effect=RuntimeError())
    )

    with pytest.raises(LogDirectoryError) as excinfo:
        setup_logging(log_file=log_file, log_directory=None)

    err = "Could not identify or create a log directory due to an error"
    assert err in str(excinfo.value)
