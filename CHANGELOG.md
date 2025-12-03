# Changelog

All notable changes to scholar-flux will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
## [0.3.0] - 12/03/2025
### Added
- The `SearchCoordinator` now includes a `parameter_search` feature that allows end-users to retrieve non-paginated API responses with a prebuilt dictionary or endpoint. This addition allows users to send requests while taking advantage of caching, retry-logic, rate limiting, and processing orchestration.
- The type expectations for metadata fields are now more specifically tailored to what can be expected for the `SearchCoordinator` (including the now optional pagination), `ProcessedResponse` models which constrains metadata types to dictionaries with string parameters.
- Introduced `ResponseMetadataMap` to standardize metadata extraction across providers. Each provider config now includes an optional `metadata_map` input that defines how to parse provider-specific metadata fields (e.g., `numFound` for PLOS, `count` for OpenAlex, `total-results` for Crossref).
- Updated the `ProviderConfig` model to allow for the use of `ResponseMetadataMaps`. When available, this field can inform users of the total number of query hits, page size within a response, and the number of remaining pages that are associated with a particular query.
- Added the `total_query_hits` and `records_per_page` properties to `ProcessedResponse`, `ErrorResponse`, `NonResponse`, and `SearchResult`. These properties expose the total number of results reported by the API and the records sent in a single response from an API, enabling smarter pagination logic and progress tracking.
- Introduced `NormalizingFieldMap` as an intermediate base class between `BaseFieldMap` and `AcademicFieldMap`. This class encapsulates the record normalization logic with an internal `NormalizingDataProcessor`, making it reusable for custom field map implementations.
- Added `PubmedSearchWorkflow` as a dedicated workflow class for PubMed's two-step retrieval process (eSearch → eFetch). This workflow automatically preserves metadata from the initial eSearch step in the final eFetch results to ensure that the complete search metadata is available to users.
- Field maps now support fallback paths via `list[str]` types. For example, `title=["MedlineCitation.Article.ArticleTitle.#text", "MedlineCitation.Article.ArticleTitle"]` will try each path sequentially until a value is found. This update resolves edge cases where field names might vary on a record-by-record basis.
- Added `get_first_available_key()` utility function for both case-sensitive and case-insensitive dictionary key extraction with fallback support.
- `ErrorResponse.normalize()` now supports graceful error handling with `raise_on_error`. If `raise_on_error=False` this method returns an empty list instead of raising an exception. This allows normalization to be attempted on mixed result sets without interrupting processing when setting `raise_on_error=False`.
- For all searches (including successful searches), ScholarFlux search coordination now directly references the last result for the current provider to wait for the specified number of seconds before sending the next request when APIs send responses with `Retry-After` headers.
- Tested all new functionality to ensure that they produce the expected output.
- Updated the metadata retrieval logic for PubMed workflows. The eSearch step's metadata (query info, ID lists, result counts) is now automatically merged into the final eFetch response.

### Changed
- **Potentially breaking** The `get_nested_data` field was previously structured to return a value as is if it was Falsy. This includes empty lists, dicts, and None. Its original behavior was tailored to extraction of values nested in dictionaries. Now its behavior is to always return None when a key isn't available in a data structure (always the case for empty containers and None.).
- The `SearchCoordinator._search_page_result()` private method is now renamed to `.search_page()` for discovery. This method returns a `SearchResult` container and can be useful in cases where additional search information is required to be stored with the result (e.g., `query`, `page`, `provider_name`).
- To ensure consistency with the SearchAPIConfig, the SearchCoordinator now uses the provider name from the last-queried URL if it exists within the registry. Otherwise, the SearchAPI.provider_name is used as usual. This change is useful in normalization scenarios where a field map is not supplied by the user, but the last queried URL differs from the current `SearchAPI.provider_name` attribute.
- Updated the Crossref provider config to indicate that Plus users need to use API-key headers rather than API key parameters. The `scholar_flux.api.providers.crossref.py` docstring gives an example of how users can manually integrate this into their workflows. Currently, no providers currently require automatic header-based authentication, but direct support for token-based headers will be directly implemented if/when needed.
- Crossref now has a default request delay of 1.0 seconds. The API has a maximum request interval of 50 requests per second for the general public, but the default is set lower to a 1.0 second request delay to account for potential API changes in the event that they ever occur.
- Path delimiters are more centralized in the `PathUtils.DELIMITER` class variable for easier coordination of JSON processing for referencing nested structures with strings.
- Implemented proactive rate limit coordination via `_respect_retry_after()`. When an API response includes a `Retry-After` or `x-ratelimit-retry-after` header (both case-insensitive), ScholarFlux now waits before sending the next request to prevent 429 errors before they could occur.
- The RetryHandler now uses the `DEFAULT_RETRY_AFTER_HEADERS` class variable to search for `Retry-After` headers, independent of case-sensitivity. As previously, if a `429` status code is sent and a `Retry-After` value can't be found, the `RetryHandler` defaults to dynamic rate limiting with a backoff factor.
- Auto-configured Redis/MongoDB session caching: `CachedSessionManager(backend='redis')` now automatically reads connection settings from environment variables (`SCHOLAR_FLUX_REDIS_HOST`, `SCHOLAR_FLUX_REDIS_PORT`, `SCHOLAR_FLUX_MONGODB_HOST`, `SCHOLAR_FLUX_MONGODB_PORT`), ensuring consistency with `DataCacheManager` storage backends.

### Fixed
- When sending multipage requests with `SearchCoordinator.search_pages`, in some circumstances, an API could send less records than expected due to rate-limiting/token limits, making it appear as if there are no more pages to be queried. A `ResponseMetadataMap`, when implemented, can now determine whether there are pages remaining to be queried or whether multipage searches should halt early.
- Updated the `SearchAPI.prepare_search` method to include the `request_delay` method to match the exact parameter set for the `search` method. This prevents potential unwarranted warnings indicating that `request_delay` isn't an API-specific config parameter (as opposed to a universal ScholarFlux parameter)- Eliminated early stoppage for record retrieval for Core API responses when less than the expected number of records are received. The coordinator now uses `total_query_hits` to determine if a partial page is limited due to token count limits per second or due to the actual number of possible, retrievable records.
- Resolved an edge case where workflows would warn users on no-longer valid parameters on switching workflows. The configuration now prevents warnings from showing when providers are switched.
- Corrected retry handler behavior to skip the final sleep delay after max retries are exhausted, reducing unnecessary wait time on failed requests.
- Changed `logging.info` usage in `PassThroughDataProcessor` to `logger.info`. Record retrieval count is now directly controllable via the package-level logger's log level.

### Documentation
- Comprehensive README refactor explaining ScholarFlux's differentiating factors, including concurrent orchestration architecture, threading model, and production-ready features.
- Revamped Sphinx tutorials to cover the core and advanced functionalities of ScholarFlux. The front-facing documentation was generated with the assistance of AI (Claude) and was human-revised for correctness. Plans for further revision are in the works where it may be helpful!


## [0.2.0] - 11/19/2025
### Added
- ScholarFlux now introduces an optional normalization method to prepare records across APIs despite provider-specific differences in response formats. Record normalization plays a pivotal role in cross-platform preparation for downstream tasks by extracting common academic fields (`title`, `doi`, `author`, `abstract`, etc.) consistently across all default providers.
- When performing a search with the SearchCoordinator, set `normalize_records=True` to automatically normalize responses during processing. The normalized data can then be extracted through `ProcessedResponse.normalized_records` or `SearchResult.normalized_records`. 
- Added the optional `field_map` attribute to `ProviderConfig` and all default provider configs. This field map is directly used by default providers to normalize processed responses into universal dictionary structures for academic APIs with applications to machine learning.
- Introduced `.normalize()` methods to `ProcessedResponse`, `SearchResult`, and `SearchResultList` for standardized record normalization.
- Improved URL normalization and provider config resolution for URLs with parameters.
- Added a new exception `RecordNormalizationException` for normalization errors.
- With tests for new functionality as well as previous path-processing utilities, test coverage now covers 96% of all functionality within ScholarFlux.

### Changed
- Organized the current set of `scholar_flux.api` exports for easier discoverability of internal functionality.
- Minor docstring and comment corrections. 
- Enhanced type annotations and flexibility for record key handling in the `DataProcessor`. It now accepts string paths, lists, or mixed formats.
- Updated the record/metadata path handling functionality in the `DataExtractor`. It can now handle and transform delimited string representations of paths.


## [0.1.5] - 11/10/2025
### Changed
- On package import and reinitialization, the `initialize_package` function now shows an actionable error message if either `config_params` or `logging_params` has an incorrect type. This change helps to quickly spot and fix mistakes on initialization, especially when reinitializing ScholarFlux.
- When an incorrect `env_path` is received on package initialization, ScholarFlux now logs a warning with `logging` and `warnings` for clarity before falling back to the default package configuration settings. In Jupyter Notebook and terminals such as IPython, this warning will display in pinkish-red and is hard to miss.
- The `setup_logging` function now accepts a `propagate_logs` argument for programmatic control of log propagation. This setting is True by default but can be set to False to prevent logs from being echoed by console-level loggers.
- Updated the documentation and configuration loader to include `SCHOLAR_FLUX_PROPAGATE_LOGS`.
- Test coverage for package initialization, logging, and configuration loading is now at 100%, and the functionality was vetted to ensure reliability and user-friendliness in supporting different setups.
- Package initialization now raises a warning with the `warnings` package if a non-fatal error occurs when loading configuration settings.
- If an error initializing scholar_flux logging occurs, the `initialize_package` function now raises a `PackageInitializationError` instead of a `ValueError`.
- Package initialization now supports a `SCHOLAR_FLUX_PROPAGATE_LOGS` environment variable and configuration option. On package initialization, this setting controls whether ScholarFlux log messages propagate to console-level loggers (such as IPython/Jupyter/VS Code). By default, propagation is enabled for compatibility with user/application logging setups.

### Fixed
- On dynamic initialization with a .env and newly set environment variables, the config loader now overrides existing variables when required.
- Fixed an edge case where the logger would not print the full range of environment variables loaded with verbose settings on configuration loading.

## [0.1.4] - 11/08/2025
### Added
- The `SearchWorkflow`, by default, now integrates the package-level `ProviderRegistry` to determine whether a provider exists and also warns ahead of time if a provider that does not exist in the registry is specified.
- Added tests to confirm that the updated workflow source code operates as intended in both common and edge cases.

### Changed
- Refactored the `WorkflowStep.pre_transform` method to use the current provider name associated with the workflow by default. The previous context is used only if a provider name isn't specified for a workflow step.
- Introduced a `stop_on_error` flag to the `SearchWorkflow` that halts workflows when a `None`, `ErrorResponse`, or `NonResponse` result from a previous step is encountered. 
- The SearchWorkflow now prioritizes its current configuration over the result from the preceding workflow step.  This prevents potential issues such as API-specific parameter values that no longer apply when switching providers. This does not affect the way that the `PubMed` workflow operates, however. The behavior can be modified by inheriting and changing the `WorkflowStep.pre_transform` logic. 
- Updated the package-level logger to be retrievable using the `logging` module. After importing scholar_flux or any submodule, it can be retrieved via `logging.getLogger("scholar_flux")`.
- Modified the `BaseDataParser` test suite to simulate the unavailability of the `xmltodict` or `yaml` dependencies and their resulting error messages when not installed.
- **Breaking**: Renamed the positional parameter, `storage` to `cache_storage`, for the constructor, `DataCacheManager.with_storage` for consistency with the rest of the implementation of the `DataCacheManager`.

### Fixed
- When encountering an optional dependency error where `xmltodict` isn't installed, the `PubMed` workflow would record that a `RuntimeError` occurred within the error message of a `NonResponse` object after naively trying to continue processing. The addition of `stop_on_error` clarifies the error in an `ErrorResponse` object with a human-readable explanation indicating the missing `xmltodict` library.
- Refactored the `MultiSearchCoordinator`'s `test_rate_limiter_normalization` test to patch the `_wait` method instead of the `sleep` method. This method retrieves the unadjusted, raw `min_interval` between successive requests before accounting for the amount of time that has already elapsed since the last request.

## [0.1.3] - 11/01/2025
### Changed
- Revised all code paths that would return `None` due to unexpected behavior during data retrieval to now return a `NonResponse` for easier management of possible search results. The `NonResponse` displays the underlying error/message and is `Falsy` (i.e., `not NonResponse` returns True).
- Extended tests to cover a wide range of scenarios when using storage backend devices for response processing cache, and when trying to import and use these storage devices without the required package dependencies.
- Updated the `SQLStorage`, `RedisStorage`, and `MongoDBStorage` classes to optionally allow users to raise an error with the `raise_on_error` attribute when encountering backend storage exceptions. By default, `raise_on_error=False`, and is, as a result, not a breaking update.
- The addition of new, comprehensive tests covering each possible search result return type and common cache storage scenarios brings test coverage from 94% to 95%.
- Modified storage cache dependency checking: we removed the SQLALCHEMY_AVAILABLE (True/False) boolean and now check the sqlalchemy module's availability directly, setting the module to None if the import fails. This pattern is now consistent with those of the Redis and MongoDB storage backends.

### Security
- Patched the dependencies list to include only package versions known to have no exploitable vulnerabilities with current CVEs.
- ScholarFlux is committed to security, and our addition of the octoscan workflow is the expression of our commitment. We'll continue to use open source security tools such as Security CLI to ensure a safe and rewarding research experience.

## [0.1.2] - 10/30/2025
### Changed
- **BREAKING**: Detailed step-by-step logging reports are now opt-in. Set `SCHOLAR_FLUX_ENABLE_LOGGING=TRUE` for file-based logs. Console logs at WARNING and above remain.
- The Default log level is now `WARNING` (was `DEBUG`). You can also modify this with `SCHOLAR_FLUX_LOG_LEVEL=DEBUG`.
- Log messages are cleaner and no longer include the module path.
- Testing and coverage reports now run in parallel for Python 3.10, 3.11, 3.12, and 3.13. We’ll add 3.14 support once dependencies are ready.


### Added
- User and Developer documentation on opt-in logging and optional dependencies
- Enhanced CONTRIBUTING.md with comprehensive logging setup instructions for developers.


## [0.1.1] - 10/29/2025
### Added
- Introduced `scholar_flux.api.models.BaseProviderDict`: a normalization-aware dictionary that resolves minor variations in provider names spelling to the right provider.
- Introduced `RateLimiterRegistry`: Inherits from the BaseProviderDict and strictly maps providers to rate limiters, raising an error if a non-rate limiter is encountered.
- Added tests for `BaseProviderDict` and its subclasses.
- Added tests and logging revisions to MongoDBStorage and SQLStorage.
- Added `SearchAPI.prepare_search`: A helper method that returns a `requests.PreparedRequest` object, indicating how the request was prepared.

### Changed
- Refactored `ProviderRegistry` and rate limiter registries to directly inherit from the `BaseProviderDict` for consistent provider name normalization.
- Updated the `MultiSearchCoordinator` to directly and always use the provider's recorded minimum request delay from the `threaded_rate_limiter_registry`.
- Updated the docstring of `MultiSearchCoordinator` to include a usage example and details on shared rate limiting.
- Updated the CLI representation of `RateLimiter` and `ThreadedRateLimiter` instances to display the class name and minimum interval for easier debugging.
- Modified the rate limiter to use `min_interval` as a property with a setter - this change ensures that `min_interval` is validated the moment it is set and raises an APIParameterException when encountering values other than `float`/`int`/`None`.
- Stashed a feature that would allow Class/Instance level control over unknown API-specific parameters in `APIParameterConfig`. Currently, unknown parameters are filtered by default for safety. This feature can be revisited if more flexible parameter handling is needed in the future.

## [0.1.0] - 10/26/2025
### Added
- Github Workflows now support uploads to pypi
- In future patches, we'll aim to document and continue working toward backward compatibility in future releases to minimize breaking changes on updates

### Security
- The pre-initialized scholar_flux.masker now uses a `FuzzyKeyMaskingPattern` to mask email strings in parameter
  dictionaries. This pattern will mask email fields that are named some after variation of the word, `mail`, during
  request retrieval.
