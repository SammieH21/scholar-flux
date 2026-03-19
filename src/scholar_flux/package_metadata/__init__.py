"""The scholar_flux.package_metadata module is a helper module that holds information relevant to the initialization and
storage of data related to the scholar_flux package.

At the moment, the package_metadata module has two responsibilities:

1. Retrieving the current version number of the scholar_flux package from the importlib module
2. Indicating the first available writable directory dedicated to scholar_flux cache.

For directory cache, the following directories are prioritized in the following order:

1. The scholar_flux/package_directory for cache and scholar_flux/logs for logging

Otherwise:

2. The ~/.scholar_flux/package_cache directory for cache and ~/.scholar_flux/logs for logging

The first writable directory will then be used for setting up default locations for requests and response cache.

"""

from scholar_flux.package_metadata.directories import PackageDirectorySettings
from importlib.metadata import PackageNotFoundError

try:
    from importlib import metadata as _md

    __version__ = _md.version("scholar_flux")
# If the package cannot be found, assume local development
except (PackageNotFoundError, ImportError):
    __version__ = "0.0.0+local"

package_directory_settings = PackageDirectorySettings()

get_default_writable_directory = package_directory_settings.get_default_writable_directory

__all__ = ["__version__", "PackageDirectorySettings", "get_default_writable_directory"]
