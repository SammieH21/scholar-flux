from scholar_flux.utils.logger import setup_logging
from scholar_flux.exceptions import LogDirectoryError
from unittest.mock import MagicMock
import logging
import pytest


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


def test_logging_directory_setup_failure(monkeypatch, caplog):
    """Tests whether unsuccessfully setting up a logger will raise the required exception"""
    log_file = "app.log"
    monkeypatch.setattr(
        "scholar_flux.utils.logger.get_default_writable_directory", MagicMock(side_effect=RuntimeError())
    )

    with pytest.raises(LogDirectoryError) as excinfo:
        setup_logging(log_file=log_file, log_directory=None)

    err = "Could not identify or create a log directory due to an error"
    assert err in str(excinfo.value)
    assert err in caplog.text
