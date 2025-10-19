# /utils/module_utils.py
"""The scholar_flux.utils.module_utils module defines the `set_public_api_module` that is used throughout the
scholar_flux source code to aid in logging and streamline the documentation of imports.

It is generally used in the initialization of submodules within the scholar_flux which helps greatly in the structuring
of the automatic sphinx documentation.

"""


def set_public_api_module(module_name: str, public_names: list[str], namespace: dict):
    """Assigns the current module's name to the __module__ attribute of public API objects.

    This function is useful for several use cases including sphinx documentation, introspection, and
    error handling/reporting.

    For all objects defined in the list of a modules public API names (generally named __all__),
    this function sets their __module__ attribute to the name of the current public API module
    if supported.

    This is useful for ensuring that imported classes and functions appear as if they are defined in
    the current module (such as in the automatic generation of sphinx documentation), which improves
    overall documentation, introspection, and error reporting.

    Args:
        module_name (str): The name of the module (usually __name__).
        public_names (list[str]): List of public object names to update (e.g., __all__).
        namespace (dict): The module's namespace (usually globals()).

    Example usage:
        set_public_api_module(__name__, __all__, globals())

    """
    for name in public_names:
        obj = namespace[name]
        if hasattr(obj, "__module__"):
            obj.__module__ = module_name


__all__ = ["set_public_api_module"]
