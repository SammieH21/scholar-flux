# /utils
"""The scholar_flux.utils module contains a comprehensive set of utility tools used to simplify the re-implementation of
common design patterns.

Modules:
    - initializer.py: Contains the tools used to initialize (or reinitialize) the scholar_flux package.
                      The initializer creates the following package components:
                        - config: Contains a list of environment variables and defaults for configuring the package
                        - logger: created by calling setup_logging function with inputs or defaults from an .env file
                        - masker: identifies and masks sensitive data from logs such as api keys and email addresses

    - logger.py: Contains the setup_logging that is used to set the logging level and output location for logs when
                 using the scholar_flux package

    - config.py: Holds the ConfigLoader class that starts from the scholar_flux defaults and reads from an .env and
                 environment variables to automatically apply API keys, encryption settings, the default provider, etc.

    - helpers.py: Contains a variety of convenience and helper functions used throughout the scholar_flux package.

    - file_utils.py: Implements a JsonFileUtils class that contains several static methods for reading files

    - encoder: Contains an implementation of a CacheDataEncoder and JsonDataEncoder that uses base64 and json utilities
               to recursively serialize, deserialize, encode and decode JSON dictionaries and lists for storage and retrieval
               by using base64. This method accounts for when direct serialization isn't possible and would otherwise
               result in a JSONDecodeError as a direct result of not accounting for nested structures and types.

    - json_processing_utils: Contains a variety of utilities used in the creation of the RecursiveJsonProcessor which
                             is used to streamline the process of filtering and flattening parsed record data

    - /paths: Contains custom implementations for processing JSON lists using path processing that abstracts
              elements of JSON files into Nodes consisting of paths (keys) to arrive at terminal entries (values)
              similar to dictionaries. This implementation simplifies the flattening processing, and filtering of
              records when processing articles and record entries from response data.

    - provider_utils: Contains the ProviderUtils class that implements class methods that are used to dynamically read
                      modules containing provider-specific config models. These config models are then used by
                      the scholar_flux.api module to populate Search API configurations with API-specific settings.

    - repr_utils: Contains a set of helper functions specifically geared toward printing nested objects and
                  compositions of classes into a human readable format to create sensible representations of objects

"""

from scholar_flux.utils.logger import setup_logging
from scholar_flux.utils.config_loader import ConfigLoader
from scholar_flux.utils.initializer import config_settings, initialize_package

from scholar_flux.utils.json_file_utils import JsonFileUtils
from scholar_flux.utils.encoder import CacheDataEncoder, JsonDataEncoder

from scholar_flux.utils.helpers import (
    get_nested_data,
    nested_key_exists,
    generate_response_hash,
    coerce_int,
    coerce_str,
    try_str,
    try_int,
    try_dict,
    try_pop,
    get_first_available_key,
    try_call,
    as_list_1d,
    unlist_1d,
    is_nested,
    get_values,
    is_nested_json,
    try_quote_numeric,
    quote_numeric,
    quote_if_string,
    generate_iso_timestamp,
    format_iso_timestamp,
    parse_iso_timestamp,
)

from scholar_flux.utils.paths import (
    ProcessingPath,
    PathNode,
    PathSimplifier,
    PathNodeMap,
    RecordPathNodeMap,
    RecordPathChainMap,
    PathNodeIndex,
    PathProcessingCache,
    PathDiscoverer,
)

from scholar_flux.utils.module_utils import set_public_api_module

from scholar_flux.utils.json_processing_utils import (
    PathUtils,
    KeyDiscoverer,
    KeyFilter,
    RecursiveJsonProcessor,
    JsonRecordData,
    JsonNormalizer,
)


from scholar_flux.utils.repr_utils import (
    truncate,
    generate_repr,
    generate_repr_from_string,
    format_repr_value,
    normalize_repr,
    adjust_repr_padding,
)

from scholar_flux.utils.response_protocol import ResponseProtocol

import importlib

_lazy_imports = {("scholar_flux.utils.provider_utils", "ProviderUtils")}


def __getattr__(name: str):
    """Enables the lazy retrieval of objects within the `scholar_flux.utils` module's namespace that are not loaded
    until they are explicitly needed by a package resource or by user."""
    try:
        module, object_name = next(
            ((module, object_name) for (module, object_name) in _lazy_imports if object_name == name)
        )
        imported_module = importlib.import_module(module)
        current_object = getattr(imported_module, object_name, None)
        globals()[name] = current_object
        return current_object
    except (ModuleNotFoundError, NameError, ValueError, AttributeError, StopIteration) as e:
        raise AttributeError(f"'{name}' could not be imported from module, '{__name__}': {e}")


__all__ = [
    "setup_logging",
    "ConfigLoader",
    "config_settings",
    "CacheDataEncoder",
    "JsonDataEncoder",
    "get_nested_data",
    "nested_key_exists",
    "get_first_available_key",
    "generate_response_hash",
    "coerce_str",
    "coerce_int",
    "try_str",
    "try_int",
    "try_dict",
    "try_pop",
    "try_call",
    "as_list_1d",
    "unlist_1d",
    "is_nested",
    "get_values",
    "is_nested_json",
    "try_quote_numeric",
    "quote_numeric",
    "quote_if_string",
    "JsonFileUtils",
    "KeyDiscoverer",
    "KeyFilter",
    "RecursiveJsonProcessor",
    "JsonNormalizer",
    "JsonRecordData",
    "PathUtils",
    "ProcessingPath",
    "PathNode",
    "PathSimplifier",
    "PathNodeMap",
    "RecordPathNodeMap",
    "RecordPathChainMap",
    "PathNodeIndex",
    "PathProcessingCache",
    "PathDiscoverer",
    "truncate",
    "generate_repr",
    "generate_repr_from_string",
    "format_repr_value",
    "normalize_repr",
    "adjust_repr_padding",
    "ResponseProtocol",
    "initialize_package",
    "generate_iso_timestamp",
    "format_iso_timestamp",
    "parse_iso_timestamp",
    "set_public_api_module",
]


def __dir__() -> list[str]:
    """Implements a basic `dir` method for the current directory.

    Represents the available modules and objects that are available for import and use within the current module.

    """
    return list(globals().keys()) + [object_name for (_, object_name) in _lazy_imports]  # noqa: C417
