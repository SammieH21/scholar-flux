# /package_metadata/directories.py
"""The scholar_flux.package_metadata.directories module implements the `get_default_writable_directory` function that is
used to determine the default directory to use for caching and logging based on whether it is writeable."""
from pathlib import Path
from typing import Optional, Literal
import os


def _get_default_readable_directory_candidates():
    """Returns candidate parent directories in priority order for read operations."""

    # Ground truth location for the configuration of the `scholar_flux` package
    env_home = os.getenv("SCHOLAR_FLUX_HOME")

    # nested directory for package cache and logging
    hidden_directory = ".scholar_flux"
    package_directory = Path(__file__).parent.parent

    candidates = [Path.cwd(), Path.home() / hidden_directory, Path.cwd() / hidden_directory, package_directory]

    # 1. Environment variable override
    candidates = [Path(env_home)] + candidates if env_home else candidates

    return candidates


def _get_default_writable_directory_candidates(directory_type: str):
    """Returns potentially writable candidate parent directories in priority order."""

    if directory_type == "env":
        return _get_default_readable_directory_candidates()

    # Ground truth location for the configuration of the `scholar_flux` package
    env_home = os.getenv("SCHOLAR_FLUX_HOME")

    # nested directory for package cache and logging
    hidden_directory = ".scholar_flux"
    package_directory = Path(__file__).parent.parent

    # defines a hidden directory and home directory as a candidate for the `.scholar_flux` directory
    # ensure that an env only sits in the current working directory as opposed to a nested directory
    hidden_directories = [Path.home() / hidden_directory, Path.cwd() / hidden_directory, package_directory]

    # Environment variable override
    candidates = [Path(env_home)] + hidden_directories if env_home else hidden_directories

    return candidates


def get_default_writable_directory(
    directory_type: Literal["package_cache", "logs", "env"],
    subdirectory: Optional[str | Path] = None,
    *,
    default: Optional[Path] = None,
) -> Path:
    """This is a helper function that, in case a default directory is not specified for caching and logging in package-
    specific functionality, it can serve as a fallback, identifying writeable package directories where required.

    Args:
        directory_type (Literal['package_cache','logs', "env"])
        subdirectory (Optional[str | Path]): A path within the default directory to create. the scholar_flux package
                                             will default `package_cache` and `logs` subdirectory names to there
                                             directory_type while `env` directories will use the parent directory.
                                             unless explicitly defined.
        default: (Optional[str | Path]): Defines an optional path to use when none of the default directories are
                                         available. if left None, this function will raise a runtime exception when
                                         the package default directories are not writeable.
    Returns:
        Path: The path of a default writeable directory if found

    Raises:
        RuntimeError if a writeable directory cannot be identified

    """

    if directory_type not in ["package_cache", "logs", "env"]:
        raise ValueError("Received an incorrect directory_type when identifying writable directories.")

    for base_path in _get_default_writable_directory_candidates(directory_type):
        try:
            # default to the `package_cache` and `logs` subdirectory names if `subdirectory` isn't specified
            # otherwise uses the parent directory
            current_subdirectory = subdirectory or (
                directory_type if directory_type in ("package_cache", "logs") else Path()
            )

            full_path = base_path / current_subdirectory

            create_parent_directories = directory_type != "env"
            # Test writeability if `create_parent_directories is True
            full_path.mkdir(parents=create_parent_directories, exist_ok=True)
            return full_path

        except (PermissionError, OSError, TypeError):
            continue

    if default:
        return Path(default)

    raise RuntimeError(f"Could not locate a writable {directory_type} directory for scholar_flux")


__all__ = ["get_default_writable_directory"]
