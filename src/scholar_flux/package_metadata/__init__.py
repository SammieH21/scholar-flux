from importlib.metadata import PackageNotFoundError

try:
    from importlib import metadata as _md

    __version__ = _md.version("scholar_flux")
except (PackageNotFoundError, ImportError):  # Catch both  and ImportError
    __version__ = "0.0.0+local"

from scholar_flux.package_metadata.directories import get_default_writable_directory

__all__ = ["__version__", "get_default_writable_directory"]
