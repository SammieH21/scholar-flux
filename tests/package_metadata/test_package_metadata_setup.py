import pytest
from unittest.mock import patch
import importlib
from importlib.metadata import PackageNotFoundError
import scholar_flux.package_metadata


@pytest.fixture
def restore_package_metadata_version_defaults():
    """Restores package metadata version defaults after test completion."""
    yield
    importlib.reload(scholar_flux.package_metadata)


def test_package_versioning(restore_package_metadata_version_defaults):
    """Verifies that importlib.metadata.version, when successful, sets `scholar_flux.package_metadata.__version__`."""
    with patch("importlib.metadata.version", return_value="1.0.0t"):
        importlib.reload(scholar_flux.package_metadata)
        from scholar_flux.package_metadata import __version__

        assert __version__ == "1.0.0t"


def test_package_incorrect_versioning(restore_package_metadata_version_defaults):
    """Verifies that __version__ defaults to `0.0.0+local` when an import error occurs during metadata loading."""
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        importlib.reload(scholar_flux.package_metadata)
        from scholar_flux.package_metadata import __version__

        assert __version__ == "0.0.0+local"
