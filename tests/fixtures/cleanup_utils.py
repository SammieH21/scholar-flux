"""Defines the `cleanup` helper used to ensure that temporary files/directories are removed after each test."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="function")
def cleanup(tmp_path: Path) -> Iterator[None]:
    """A helper utility that cleans up temporary files and directories created with `tmp_path` after each test."""
    yield
    # Remove all files and directories inside tmp_path
    for root, dirs, files in os.walk(tmp_path, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


__all__ = ["cleanup"]
