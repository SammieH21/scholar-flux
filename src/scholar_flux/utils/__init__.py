"""

The scholar_flux.utils module contains a comprehensive set of utility tools used to simplify the re-implementation
of common design patterns.

Modules:
    - initializer.py: Contains the tools used to initialize (or reinitialize) the scholar_flux package.
                      The initializer creates the following package components:
                        - config: Contains a list of environment variables and defaults for configuring the package
                        - logger: created by calling setup_logging function with inputs or defaults from an .env file
                        - masker: identifies and masks sensitive data from logs such as api keys and email addresses

    - logger.py: Contains the setup_logging that is used to set the logging level and output location for logs when
              using the the scholar_flux package

    - config.py: Holds the ConfigLoader class that starts from the scholar_flux defaults and reads from an .env and
                 environment variables to automatically apply API keys, encryption settings, the default provider, etc.

    - helpers.py: Contains a variety of convenience and helper functions used throughout the scholar_flux package.

    - file_utils.py: Implements a FileUtils class that contains several static methods for reading files

    - encoder: Contains an implementation of a CacheDataEncoder that uses base64 utilities  to recursively encode
               and decode JSON dictionaries and lists for storage and retrieval by using base64. This method accounts
               for when direct serialization isn't possible. Without accounting for nested structures and types.

    - data_processing_utils: Contains a variety of utilities used in the creation of the RecursiveDictProcessor which
                             is used to streamline the process of filtering and flattening parsed record data

    - /paths: Contains custom implementations for processing JSON lists using path processing that abstracts
              elements of JSON files into Nodes consisting of paths (keys) to arrive at terminal entries (values)
              similar to dictionaries. This implementation simplifies the flattening processing, and filtering of
              records when processing articles and record entries from response data.

    - repr_utils: Contains a set of helper functions specifically geared toward printing nested objects and
                  compositions of classes into a human readable format to create sensible representations of objects

"""

from scholar_flux.utils.logger import setup_logging
from scholar_flux.utils.config_loader import ConfigLoader
from scholar_flux.utils.initializer import config_settings, initialize_package

from scholar_flux.utils.file_utils import FileUtils
from scholar_flux.utils.encoder import CacheDataEncoder

from scholar_flux.utils.helpers import (
    get_nested_data,
    nested_key_exists,
    generate_response_hash,
    try_int,
    try_dict,
    try_pop,
    try_call,
    as_list_1d,
    unlist_1d,
    is_nested,
    try_quote_numeric,
    quote_numeric,
    quote_if_string,
)

from scholar_flux.utils.paths import (
    ProcessingPath,
    PathNode,
    PathSimplifier,
    PathNodeMap,
    PathNodeIndex,
    ProcessingCache,
    PathDiscoverer,
)

from scholar_flux.utils.data_processing_utils import (
    PathUtils,
    KeyDiscoverer,
    KeyFilter,
    RecursiveDictProcessor,
    JsonNormalizer,
)


from scholar_flux.utils.repr_utils import (
    generate_repr,
    generate_repr_from_string,
    format_repr_value,
    adjust_repr_padding,
)

__all__ = [
    "setup_logging",
    "ConfigLoader",
    "config_settings",
    "CacheDataEncoder",
    "get_nested_data",
    "nested_key_exists",
    "generate_response_hash",
    "try_int",
    "try_dict",
    "try_pop",
    "try_call",
    "as_list_1d",
    "unlist_1d",
    "is_nested",
    "try_quote_numeric",
    "quote_numeric",
    "quote_if_string",
    "FileUtils",
    "ProcessingPath",
    "PathNode",
    "PathSimplifier",
    "PathNodeMap",
    "PathNodeIndex",
    "ProcessingCache",
    "PathDiscoverer",
    "PathUtils",
    "KeyDiscoverer",
    "KeyFilter",
    "RecursiveDictProcessor",
    "JsonNormalizer",
    "generate_repr",
    "generate_repr_from_string",
    "format_repr_value",
    "adjust_repr_padding",
    "initialize_package",
]
