"""Test module for verifying the behavior and functionality of the `PackageDirectorySettings` model."""

from scholar_flux.package_metadata import PackageDirectorySettings, package_directory_settings
from pathlib import Path
import pytest
from tests.testing_utilities import raise_error
import re


def test_default_home_directory_name_setting():
    """Verifies that the default package directory home is set correctly."""

    package_dir = package_directory_settings.package_directory
    assert package_dir.name.endswith("scholar_flux")
    assert package_dir.exists()


def test_default_directory_classvar_settings():
    """Verifies that the default package directory home is set correctly."""
    assert PackageDirectorySettings.DEFAULT_PACKAGE_NAME == "scholar_flux"
    assert package_directory_settings.home_env_var == "SCHOLAR_FLUX_HOME"
    assert package_directory_settings.package_directory == PackageDirectorySettings.DEFAULT_PACKAGE_SOURCE_DIRECTORY
    assert package_directory_settings.hidden_directory_name == f".{PackageDirectorySettings.DEFAULT_PACKAGE_NAME}"


def test_package_env_home_readable_directory_settings(tmp_path, cleanup, monkeypatch):
    """Verifies that the `SCHOLAR_FLUX_HOME` env variable is used to select a readable home directory."""

    with monkeypatch.context() as m:
        assert package_directory_settings.package_env_home is None
        readable_directory_candidates_without_env_home = (
            package_directory_settings._get_default_readable_directory_candidates()
        )
        assert readable_directory_candidates_without_env_home[0] is not None

        m.setenv(package_directory_settings.home_env_var, tmp_path)
        assert isinstance(package_directory_settings.package_env_home, Path)

        assert package_directory_settings.package_env_home == tmp_path

        readable_directory_candidates = package_directory_settings._get_default_readable_directory_candidates()

        assert package_directory_settings.package_env_home == readable_directory_candidates[0]

        assert readable_directory_candidates_without_env_home == readable_directory_candidates[1:]


@pytest.mark.parametrize("directory_type", ("package_cache", "logs", "env"))
def test_package_env_home_writable_directory_settings(directory_type, tmp_path, cleanup, monkeypatch):
    """Verifies that the `SCHOLAR_FLUX_HOME` env variable is used to find a writable scholar-flux home directory."""

    with monkeypatch.context() as m:
        assert package_directory_settings.package_env_home is None

        writable_directory_candidates_without_env_home = (
            package_directory_settings._get_default_writable_directory_candidates(directory_type)
        )
        assert writable_directory_candidates_without_env_home[0] is not None

        m.setenv(package_directory_settings.home_env_var, tmp_path)
        assert isinstance(package_directory_settings.package_env_home, Path)

        assert package_directory_settings.package_env_home == tmp_path

        writable_directory_candidates = package_directory_settings._get_default_writable_directory_candidates(
            directory_type
        )
        assert package_directory_settings.package_env_home == writable_directory_candidates[0]

        assert writable_directory_candidates_without_env_home == writable_directory_candidates[1:]


def test_get_writable_directory_with_unknown_directory_type():
    """Tests that a ValueError is raised when attempting to find a writable directory for an unknown directory type."""
    directory_type = "unknown_directory_type"
    err = re.escape(f"Received an incorrect directory_type ({directory_type}) when identifying writable directories.")
    with pytest.raises(ValueError, match=err):
        package_directory_settings.get_default_writable_directory(directory_type=directory_type)  # type: ignore


def test_package_directory_verification(tmp_path, cleanup):
    """Verifies that the `PackageDirectorySettings.verify_directory` classmethod verifies directory writability."""
    assert tmp_path.exists()
    new_dir = tmp_path / "a_test_directory"
    assert not new_dir.exists()
    verified_dir = PackageDirectorySettings.verify_directory(new_dir)
    assert new_dir == verified_dir and verified_dir.exists()

    # exists_ok=True used under the hood with Path.mkdir
    assert PackageDirectorySettings.verify_directory(str(verified_dir)) == verified_dir


def test_writable_directory_identification_failure_raises_runtime_error(monkeypatch):
    """Verifies that a runtime error is raised if directory identification fails without a fallback default."""

    err = "Could not locate a writable logs directory for scholar_flux"
    monkeypatch.setattr(
        PackageDirectorySettings, "verify_directory", raise_error(PermissionError, "Directly raised exception")
    )
    with pytest.raises(RuntimeError, match=err):
        _ = package_directory_settings.get_default_writable_directory(directory_type="logs")

    err = "Could not locate a writable package_cache directory for scholar_flux"
    with pytest.raises(RuntimeError, match=err):
        _ = package_directory_settings.get_default_writable_directory(directory_type="package_cache")


def test_writable_directory_identification_failure_with_default_returns(tmp_path, cleanup, monkeypatch):
    """Verifies that the user-specified default (fallback) directory is returned if directory identification fails."""

    monkeypatch.setattr(
        PackageDirectorySettings, "verify_directory", raise_error(PermissionError, "Directly raised exception")
    )

    package_cache_dir = package_directory_settings.get_default_writable_directory(
        directory_type="package_cache", default=tmp_path / "package_cache"
    )
    assert package_cache_dir.parent == tmp_path and package_cache_dir.name == "package_cache"

    logs_dir = package_directory_settings.get_default_writable_directory(
        directory_type="logs", default=tmp_path / "logs"
    )
    assert logs_dir.parent == tmp_path and logs_dir.name == "logs"
