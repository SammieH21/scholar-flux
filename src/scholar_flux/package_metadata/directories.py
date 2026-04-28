# /package_metadata/directories.py
"""The scholar_flux.package_metadata.directories module implements `PackageDirectorySettings` for directory settings.

This model is initialized on package startup at the package level, using the
`PackageDirectorySettings.get_default_writable_directory` method to determine the default directory to use for caching
and logging based on whether it is writable.

"""
from pathlib import Path
from typing import ClassVar, Literal, Optional

import os

from pydantic import BaseModel, Field


class PackageDirectorySettings(BaseModel):
    """Directory configuration settings used during package initialization to determine writable package directories.

    Args:
        hidden_directory_name (str):
            The name of the hidden directory for package data where files will be stored.
        package_directory (Path):
            The path to the `scholar-flux` package directory.
        home_env_var (str):
            The name of the environment variable used to determine the parent directory for the package.

    """

    hidden_directory_name: str = Field(
        default_factory=lambda: f".{PackageDirectorySettings.DEFAULT_PACKAGE_NAME}",
        description="The default parent directory name used for storing logs/cache",
    )
    package_directory: Path = Field(
        default_factory=lambda: PackageDirectorySettings.DEFAULT_PACKAGE_SOURCE_DIRECTORY,
        description="The location of the package directory where source code and tests are stored.",
    )

    home_env_var: str = Field(
        default="SCHOLAR_FLUX_HOME", description="Environment variable defining the user-specified cache/log directory"
    )
    DEFAULT_PACKAGE_SOURCE_DIRECTORY: ClassVar[Path] = Path(__file__).parent.parent
    DEFAULT_PACKAGE_NAME: ClassVar[str] = "scholar_flux"

    @property
    def package_env_home(self) -> Optional[Path]:
        """Resolves the user-specified package `home_env` variable for storing logs, caching, and configuration."""
        env_home = os.getenv(self.home_env_var)
        return Path(env_home).expanduser() if env_home else None

    def _get_default_readable_directory_candidates(self) -> list[Path]:
        """Returns candidate parent directories in priority order for read operations."""
        env_home = self.package_env_home
        candidates = [
            Path.cwd(),
            Path.home() / self.hidden_directory_name,
            Path.cwd() / self.hidden_directory_name,
            self.package_directory,
        ]
        return [env_home] + candidates if env_home is not None else candidates

    def _get_default_writable_directory_candidates(self, directory_type: str) -> list[Path]:
        """Returns potentially writable candidate parent directories in priority order."""
        if directory_type == "env":
            return self._get_default_readable_directory_candidates()

        env_home = self.package_env_home
        hidden_directories = [
            Path.home() / self.hidden_directory_name,
            Path.cwd() / self.hidden_directory_name,
            self.package_directory,
        ]
        return [env_home] + hidden_directories if env_home else hidden_directories

    @classmethod
    def verify_directory(cls, path: str | Path, create_parent_directories: bool = False) -> Path:
        """Uses `pathlib.Path` to verify that the current directory is writable by attempting to create the directory.

        Args:
            path (str| Path):
                The directory to check. The string paths are converted into a `pathlib.Path` objects before directory
                verification.
            create_parent_directories (bool):
                Indicates whether parent directories should be created if they do not already exist.

        Returns:
            Path: The original path if the directory is writable.

        Raises:
            PermissionError: If the directory is not writable due to a permissions error.
            OSError: If an OSError occurs when attempting to create the directory.
            TypeError: If an incorrect type is passed to `Path` or `Path.mkdir`.

        """
        current_path = Path(path).expanduser()

        current_path.mkdir(parents=create_parent_directories, exist_ok=True)
        return current_path

    def get_default_writable_directory(
        self,
        directory_type: Literal["package_cache", "logs", "env"],
        subdirectory: Optional[str | Path] = None,
        *,
        default: Optional[Path] = None,
    ) -> Path:
        """Determines the default directory to use for storing package cache, logs, and environment variables.

        In the case where a default directory is not specified for caching and logging in package-specific
        functionality, this method serves as a fallback, identifying writable package directories when required.

        Args:
            directory_type (Literal['package_cache','logs', "env"]):
                The functionality that a writable directory is being created for.
            subdirectory (Optional[str | Path]):
                The name or folder path to create within the default directory. By default, the scholar_flux package creates
                `package_cache` and `logs` subdirectories for caching and logging, respectively, while environment variables
                are read directly from a `.env` file if placed within the parent directory.
            default (Optional[Path]):
                Defines an optional path to use when none of the default directories are available. If None, this function
                will raise a `RuntimeError` when the package default directories are not writable.

        Returns:
            Path: The path of a default writable directory if found.

        Raises:
            RuntimeError if a writable directory cannot be identified.

        """
        if directory_type not in ("package_cache", "logs", "env"):
            raise ValueError(
                f"Received an incorrect directory_type ({directory_type}) when identifying writable directories."
            )

        for base_path in self._get_default_writable_directory_candidates(directory_type):
            try:
                # default to the `package_cache` and `logs` subdirectory names if `subdirectory` isn't specified
                # otherwise uses the parent directory
                current_subdirectory = subdirectory or (
                    directory_type if directory_type in ("package_cache", "logs") else Path()
                )
                full_path = base_path / current_subdirectory
                create_parent_directories = directory_type != "env"
                # Test writability if `create_parent_directories` is True
                return self.verify_directory(full_path, create_parent_directories=create_parent_directories)
            except (PermissionError, OSError, TypeError):
                continue

        if default:
            return Path(default).expanduser()

        raise RuntimeError(f"Could not locate a writable {directory_type} directory for {self.DEFAULT_PACKAGE_NAME}")


__all__ = ["PackageDirectorySettings"]
