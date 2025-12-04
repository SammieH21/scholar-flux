"""The scholar_flux.package_metadata module is a helper module that holds information relevant to the initialization and
storage of data related to the scholar_flux package.

At the moment, the package_metadata module has two responsibilities:

1. Retrieving the current version number of the scholar_flux package from the importlib module
2. Indicating the first available writeable directory dedicated to scholar_flux cache.
for directory cache, the following directories are prioritized in the following order.

Prioritization is given to:

1. The scholar_flux/package_directory for cache and scholar_flux/logs for logging

And otherwise:

2. The ~/.scholar_flux/package_cache directory for cache and ~/.scholar_flux/logs for logging

The first writeable directory will then be used for setting up default locations for requests and response cache.

"""

from importlib.metadata import PackageNotFoundError

try:
    from importlib import metadata as _md

    __version__ = _md.version("scholar_flux")
except (PackageNotFoundError, ImportError):  # Catch both and ImportError
    __version__ = "0.0.0+local"

from scholar_flux.package_metadata.directories import get_default_writable_directory

__all__ = ["__version__", "get_default_writable_directory"]
