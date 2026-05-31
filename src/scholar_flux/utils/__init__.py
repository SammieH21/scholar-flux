# /utils
"""The scholar_flux.utils module defines several utilities for simplifying the implementation of common design patterns.

Modules:
    - initializer.py: Contains the tools used to initialize (or reinitialize) the scholar_flux package.
                      The initializer creates the following package components:
                        - config: Contains a list of environment variables and defaults for configuring the package
                        - logger: created by calling setup_logging function with inputs or defaults from a .env file
                        - masker: identifies and masks sensitive data from logs such as API keys and email addresses

    - logger.py: Contains the setup_logging that is used to set the logging level and output location for logs when
                 using the scholar_flux package

    - config.py: Holds the ConfigLoader class that starts from the scholar_flux defaults and reads from a .env and
                 environment variables to automatically apply API keys, encryption settings, the default provider, etc.

    - helpers.py: Contains a variety of convenience and helper functions used throughout the scholar_flux package.

    - file_utils.py: Implements a JsonFileUtils class that contains several static methods for reading files

    - encoder: Contains an implementation of a CacheDataEncoder and JsonDataEncoder that uses base64 and json utilities
               to recursively serialize, deserialize, encode and decode JSON dictionaries and lists for storage and
               retrieval by using base64. This method accounts for when direct serialization isn't possible and would
               otherwise result in a JSONDecodeError as a result of not accounting for nested structures and types.

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
                  compositions of classes into a human-readable format to create sensible representations of objects

    - settings_utils: Implements a custom `SettingsDict` compatible with Pydantic. Integrates the package-level
                      masker to ensure that potentially sensitive information isn't leaked to the console when printed

"""

from scholar_flux.utils.logger import setup_logging, log_level_context, resolve_log_stream, resolve_log_level
from typing import Any
from scholar_flux.utils.config_loader import ConfigLoader
from scholar_flux.utils.initializer import config_settings, initialize_package

from scholar_flux.utils.json_file_utils import JsonFileUtils
from scholar_flux.utils.encoder import CacheDataEncoder, JsonDataEncoder

from scholar_flux.utils.helpers import (
    get_nested_data,
    nested_key_exists,
    filter_record_key_prefixes,
    infer_text_pattern_search,
    get_first_available_key,
    generate_response_hash,
    coerce_int,
    coerce_numeric,
    coerce_bool,
    coerce_str,
    coerce_bytes,
    coerce_json_str,
    coerce_flattened_str,
    handle_exception,
    with_fallback,
    try_none,
    try_str,
    try_bytes,
    try_int,
    try_dict,
    try_compile,
    try_pop,
    try_call,
    as_list_1d,
    as_tuple,
    unlist_1d,
    is_nested,
    get_values,
    is_nested_json,
    try_quote_numeric,
    quote_numeric,
    quote_if_string,
    extract_year,
    generate_iso_timestamp,
    format_iso_timestamp,
    parse_iso_timestamp,
    strip_html_tags,
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
    generate_sequence_repr,
    generate_repr_from_string,
    format_repr_value,
    normalize_repr,
    adjust_repr_padding,
)

from scholar_flux.utils.response_protocol import (
    ResponseProtocol,
    is_response_like,
    ResponseSupportsJSONProtocol,
    response_supports_json,
)

from scholar_flux.utils.settings_utils import (
    SettingsDict,
    SettingsLike,
    SettingsDictType,
)

from scholar_flux.utils.lazy_loader import lazy_import_attr

_lazy_imports = {("scholar_flux.utils.provider_utils", "ProviderUtils")}


def __getattr__(name: str) -> Any:
    """Enables the lazy retrieval of objects within the `scholar_flux.utils` module's namespace.

    These modules are not loaded until they are explicitly needed by a package resource or by a user.

    """
    return lazy_import_attr(name, _lazy_imports, __name__)


__all__ = [
    "setup_logging",
    "log_level_context",
    "resolve_log_stream",
    "resolve_log_level",
    "ConfigLoader",
    "config_settings",
    "CacheDataEncoder",
    "JsonDataEncoder",
    "get_nested_data",
    "filter_record_key_prefixes",
    "infer_text_pattern_search",
    "nested_key_exists",
    "get_first_available_key",
    "generate_response_hash",
    "coerce_str",
    "coerce_bytes",
    "coerce_json_str",
    "coerce_flattened_str",
    "coerce_int",
    "coerce_numeric",
    "coerce_bool",
    "handle_exception",
    "with_fallback",
    "try_none",
    "try_str",
    "try_bytes",
    "try_int",
    "try_dict",
    "try_compile",
    "try_pop",
    "try_call",
    "as_list_1d",
    "as_tuple",
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
    "generate_sequence_repr",
    "generate_repr_from_string",
    "format_repr_value",
    "normalize_repr",
    "adjust_repr_padding",
    "ResponseProtocol",
    "ResponseSupportsJSONProtocol",
    "response_supports_json",
    "SettingsDict",
    "SettingsLike",
    "SettingsDictType",
    "is_response_like",
    "initialize_package",
    "extract_year",
    "generate_iso_timestamp",
    "format_iso_timestamp",
    "parse_iso_timestamp",
    "strip_html_tags",
    "set_public_api_module",
]


def __dir__() -> list[str]:
    """Implements a basic `dir` method for the current directory.

    Represents the available modules and objects that are available for import and use within the current module.

    """
    return list(globals().keys()) + [object_name for (_, object_name) in _lazy_imports]  # noqa: C417
