import pytest
import os


@pytest.fixture(scope="function")
def cleanup(tmp_path):
    """A helper utility that helps to clean out any temporary files previously created for file testing"""
    """Fixture to clean up temporary files and directories after each test."""
    yield
    # Remove all files and directories inside tmp_path
    for root, dirs, files in os.walk(tmp_path, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


__all__ = ["cleanup"]
