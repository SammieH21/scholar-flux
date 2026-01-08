"""Lazy loading utilities for the scholar_flux.utils module."""

import importlib
import sys
from typing import Any


def lazy_import_attr(name: str, lazy_imports: set[tuple[str, str]], module_name: str) -> Any:
    """Lazily import an attribute from configured lazy imports.

    Args:
        name (str): Attribute name to import
        lazy_imports (set[tuple[str, str]]): Set of (module_path, object_name) tuples
        module_name (str): Name of the calling module

    Returns:
        Any: The imported object

    Raises:
        AttributeError: If the attribute cannot be found or imported
    """
    try:
        module, object_name = next(
            ((module, object_name) for (module, object_name) in lazy_imports if object_name == name)
        )
        imported_module = importlib.import_module(module)
        current_object = getattr(imported_module, object_name, None)

        # Cache in the calling module's globals
        calling_module = sys.modules[module_name]
        setattr(calling_module, name, current_object)

        return current_object
    except (ModuleNotFoundError, NameError, ValueError, AttributeError, StopIteration) as e:
        raise AttributeError(f"'{name}' could not be imported from module, '{module_name}': {e}")
