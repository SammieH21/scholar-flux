# Changelog

All notable changes to scholar-flux will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.4.0] - 01/17/2026
**Note**: While this version bump introduces substantial improvements, no major changes are necessary to migrate from version 0.3.1 to 0.4.0 (fully backward compatible).

### Added

**Normalization & Record Processing**:
- **Normalization Improvements**: Normalization now supports the retrieval of data from nested fields found in JSON structures, independent of the processing method used to prepare the data prior to normalization. Using newly implemented record annotations under the hood, records can be linked and resolved to ensure consistency in normalized outputs in a variety of processing conditions.
- **API-Aware Post-Processing**: Normalization field validation is improved via the creation of a new `_post_process` method that allows users to override how the normalization post-processing step is performed after the identification and extraction of API-specific fields. The `AcademicFieldMap` implements several minimal helper methods for extraction, including `extract_authors`, `extract_url`, `extract_abstract`, etc. Field map subclasses can use and override these methods to process and validate fields for potential downstream data engineering applications. The new `OpenAlexFieldMap` class, for example, reconstructs abstracts using the provided abstract inverted index. The `PLOSFieldMap` reconstructs article URLs by combining the `DOI` with the base URL for the API. See the `scholar_flux.api.normalization` module and docstrings for implementation details. Updated normalization documentation coming soon!
- **Optional Record ID Annotations**: `ScholarFlux` now supports using hashing for the identification of unique records in responses. This is most helpful in applications involving the deduplication of records based on their content and in cases where preprocessed and postprocessed records need to be linked to cover common normalization scenarios after transforming and filtering response records. To retrieve `ProcessedResponse.processed_records` without annotations, use `processed_records = ProcessedResponse.strip_annotations()`. For `SearchResultList` instances, use `results.join(strip_annotations=True)`.

**Observability**:
- **Rate Limiting and Retry Handling Observability**: Due to the unpredictability of API request formats, timeout errors, etc., it's often necessary to know what went wrong when the unexpected occurs. The `RetryHandler` and `RateLimiter` both now include a class-level, thread-safe `HistoryDeque` that records rate limiting durations, timestamps, and response codes to help users more easily observe how request-delays and rate limiter settings influence the time between requests to any specific API. After creating a `SearchCoordinator` and sending a request, retry-attempt history can be found at `coordinator.retry_handler.history` (or `RetryHandler.history`) and rate limiting metadata can be referenced from `coordinator.api.rate_limiter.history` (or `RateLimiter.history`). When viewing the representation or logging the object, sensitive keywords/metadata is masked by default.
- **Excessive Delay Protection**: The `RetryHandler` now raises a `RetryAfterDelayExceededException` when a server's `Retry-After` header exceeds the `RetryHandler.max_backoff` limit and the class variable, `RetryHandler.RAISE_ON_DELAY_EXCEEDED=True`. This prevents long, indefinite waits and unexplained pauses due to silent rate limits. This alert is handled at the level of the `SearchCoordinator` that then returns an `ErrorResponse` to record the error type, error message, and exact response from the API. The log and error message alerts users to adjust their configuration and limit the rate of requests made in an interval (after respecting the minimum delay). This setting can be controlled via the `scholar_flux.api.RetryHandler.RAISE_ON_DELAY_EXCEEDED` class attribute (default: `True`). On the next user-initiated search, if the previous `Retry-After` header from the same API still indicates that a delay before the next requests still remains, `ScholarFlux` will continue to respect this delay and log a message indicating the time that remains before the next request is sent.
- **History Deques for Request Monitoring**: The `scholar_flux.api.rate_limiting.history` module implements three classes created specifically for observability: the `HistoryDeque`, `RetryAttempt`, and `RateLimitEvent`. The `HistoryDeque` can store either `RetryAttempt` or `RateLimitEvent` dataclasses. This deque subclass operates as a class-level, thread-safe history, storing the last `n` (default=1000) retry attempts (for the `RetryHandler`) and rate limiting events (for the `RateLimiter` and `ThreadedRateLimiter`) while allowing transparent monitoring of outbound requests without the need to enable logging. For observability, the `HistoryDeque` implements the following methods: `create` (a factory method that creates a bounded `HistoryDeque`, storing the `HistoryDeque.DEFAULT_MAX_HISTORY` most recent entries (default=1000)), `export_history` (for converting the Deque into a list of dictionaries containing `RetryAttempt` or `RateLimitEvent` fields and masking sensitive parameters in the process), `modify_history_size` (for resizing `HistoryDeque.maxlen`), and `clear_history` (for removing all previously recorded entries).


**Storage & Caching**:
- **DuckDB Embedded Analytical Database Support**: The data storage module now includes a `DuckDBStorage` class to help support analytical workloads involving response processing cache. This class extends the `SQLAlchemyStorage` device to support embedded data storage analytics. When created, this class first checks that the `duckdb-engine` and `sqlalchemy` optional dependencies are installed and that the URI is a valid resource location for duckdb (e.g., starts with `duckdb:///`). A `DuckDBImportError` is raised if `duckdb-engine` isn't installed. As with other backends, credentials are masked if printed or logged.
- **Connection Verification**: All storage backends now support an optional `verify_connection` parameter to validate availability on initialization (this is False by default). This is helpful in cases where `MongoDB` or `Redis` connections should be used when available; otherwise, and the `InMemoryStorage` should be used.
- **Namespace Context Manager**: Response processing storage devices now come with a new `with_namespace()` context manager for temporary namespace switching. This helps with project organization when retrieving, updating, or deleting only a subset of processed records in cache.

**Security**:
- **Hardened Security Credential Masking**: This update expands log filtering and pattern masking to ensure that credentials that are commonly sent as part of database URIs are masked. `ScholarFlux` also extends the package-level `SensitiveDataMasker` defaults, taking a stricter approach to masking uncommon but otherwise possible patterns such as secret keys, GPG keys, and ssh keys. Non-strings (dictionaries, lists, base models, etc.) that are passed directly to the `logger` are also recursively masked when required. The `SensitiveDataMasker` also features a `mask_output` method that can be used to decorate and filter outputs of sensitive fields when required. The philosophy for security is simple: design for what you may need in the future, for other potential applications as well, given potential security risks with the advent of AI.
- **Optionally Mask Object Representations**: The `ABCStorage.__repr__` method now masks sensitive strings by default by using the package-level `SensitiveDataMasker` (`scholar_flux.masker`) when viewed in REPLs like the built-in python terminal, IPython, VS Code, etc. To create your own masked representations of objects, you can use the `@scholar_flux.masker.mask_output(convert_object=True)` function/method decorator to similarly recursively replace sensitive strings, API keys, tokens, emails, and other sensitive data in custom function or method output with `***`.
- **Internal Masking**: The `SECURITY.md` now includes a section that indicates how masking happens under the hood, showing that, even if sensitive strings, dicts, and other data types are logged, sensitive fields will be automatically masked beforehand.

**Developer Experience**:
- **Lazy Module Loading**: Abstracted the lazy importing logic originally used in `utils` into a separate module for easier reuse. Lazy loading is in use for `config_settings` and provider utilities and helps to prevent partial initialization errors when a feature isn't needed at import but can be helpful for end-users (e.g., importing `config_settings` directly from the front-facing `scholar_flux` API).
- **SearchCoordinator Context Management**: The `SearchCoordinator` now supports context management for temporary modifications to both search and caching configurations via the inherited `BaseCoordinator.with_components()` method. This update allows temporary component swapping, yielding a new coordinator instance without modifying the original search coordinator, enabling temporary updates to provider configurations, queries, rate limiters, processing methods, and provider-specific search-workflows on the fly.
- **Test Coverage**: This patch both improves and extends the response cache test suite to further vet functionality in the storage, retrieval, and validation of cached responses. The updated tests were expanded to cover a wider range of potential edge cases to ensure that the implementation of injectable backends functions robustly in practice. Storage test logic improvements extend to the `DataCacheManager`, existing backends (`SQLAlchemyStorage`, `RedisStorage`, `MongoDBStorage`, `InMemoryStorage`, and `NullStorage`), and the newly implemented `DuckDBStorage`.
- **BeautifulSoup 4 Optional Dependency**: `ScholarFlux` now adds the `beautifulsoup4` package module as an optional dependency for parsing and removing HTML tags from text via `scholar_flux.utils.helpers.strip_html_tags`. If installed, the `CrossrefFieldMap` post-processing step directly uses `beautifulsoup4` to parse HTML tags from text when detected. If the package module is not installed, the processed abstract text is gracefully returned without modification during normalization.

### Changed

**Normalization & Processing**:
- **Normalization Field Resolution**: Instead of instantiating a new `AcademicFieldMap` as before, each default provider now subclasses and tailors the `AcademicFieldMap` to account for the response data structure that is often unique to each API. The following classes use common post-processing methods defined in `AcademicFieldMap` or define logic tailored to the normalization of common academic fields: `ArXivFieldMap`, `CoreFieldMap`, `CrossrefFieldMap`, `OpenAlexFieldMap`, `PLOSFieldMap`, `PubMedFieldMap`, and `SpringerNatureFieldMap`. Each is implemented to stabilize the output of common fields (e.g., verifying, extracting, or reconstructing valid URLs; ensuring that abstracts are text strings instead of nested lists or indexes; transforming the `authors` field into a list consistently across providers; and others). These are designed as minimally viable yet effective, tested methods of normalization that transform formatted fields into human-readable, AI/ML-ready formats.
- **Detailed Type Aliases**: The response processing pipeline now uses targeted type aliases to ensure flexibility, uniformity, and descriptiveness of type hints used by `mypy` to vet type safety. The `scholar_flux.utils.record_types` module now implements `RecordType` + `RecordList` (parsing and processing), `NormalizedRecordType` + `NormalizedRecordList` (normalization), and `MetadataType` (extracted response metadata).
- **Recursive JSON Processing Defaults (potentially breaking)**: The `RecursiveDataProcessor` and `PathDataProcessor` classes now avoid directly joining lists of values across nested lists. While the previous default is great for terminal-based exploration, the normalization of processed records often benefits from keeping values for fields in their native data types. For the previous behavior, use `RecursiveDataProcessor(value_delimiter='; ')` or `PathDataProcessor(value_delimiter='; ')`.
- **Refactored Retrieval Pipeline Orchestration Example**: The functional pipeline example now uses a `JsonDataEncoder` to encode recursively nested structures in pandas columns into strings before storage in `.parquet` format. This implementation produces consistent results roundtrip, restoring the original columns reliably using `df.apply(JsonDataEncoder.loads)` without modifying non-encoded columns.

**API & Provider Updates**:
- **URL Validation**: Enhanced to detect whitespace in domain names. The bulk of URL validation is delegated to lower-level API clients (e.g., `requests`, `requests_cache`).
- **CORE API Default Request Delay**: Updated the default CORE API Rate limit from 6 to 10 seconds between requests and the records retrieved per request from 25 to 40. The request delay increase better mirrors the CORE API documentation for bulk record requests to more efficiently prevent Too Many Requests errors from a combination of token count limits and static/dynamic request throttling.
- **PLOS Configuration Edit**: PLOS now enables zero-indexed pagination to start record retrieval from `start=0`. This ensures that the first record is retrieved when searching or retrieving the first page for all queries.
- **PubMed Configuration Edit**: The PubMed API default provider configuration no longer indicates that an API key is required. Registering for an API key is still recommended: having a PubMed-specific API key increases the request rate limit from 3 requests per second to 10 requests per second.
- **ProviderConfig Update**: The provider configuration for each API now includes an optional `display_name` field. This field helps annotate configurations with human-readable names that are descriptive of the API being queried. If unused, this defaults to the provider name. For reference, users can use `scholar_flux.api.providers.get_display_name` to resolve a registered provider to a human-readable API name when available.
- **API Identification Convenience Features**: The `SearchAPI` now includes a `display_name` property for indicating a human-readable description of the current API. The `SearchCoordinator` also references the `display_name` and `provider_name` and properties from the API for convenience. The display name is used for logging search successes and failures for easier observability. When a `SearchResult` object is created, the display name is directly referenced from the registry of known API providers and falls back to the `provider_name` when not available.

**Storage Optimization**:
- **MongoDB Optimization**: The `MongoDBStorage` device now lazily creates the TTL index when needed (rather than on initialization). This allows connections to be validated lazily only when required (e.g., waiting until the MongoDB server is started). For the previous behavior, use validate_connection=True to raise an error on initialization if a connection can't be established on the host and port.

**Security & Dependencies**:
- **CVE Mitigation**: `ScholarFlux` continues to emphasize security as a first-class citizen, using Safety CLI and Octoscan to identify package vulnerabilities and known CVEs. Given the recently discovered CVE-2026-21441 affecting `urllib3` v2.6.2 (required for the `requests` module), `urllib3>=v2.6.3` is made an explicit dependency to mitigate potential security issues.

### Improved
- Added test coverage for new features (record annotation, record normalization, storage verification, observability, DuckDB storage, etc.) and existing features (security/masking, configuration management, and logging, API ergonomics, etc.) increasing test coverage from 96% to 97%.
- Improved documentation, grammar, and type hints throughout.
- Verified explicit support for Python 3.14 via `pytest`, `mypy`/`ruff`, and integration testing

### Fixed
- The `APIParameterConfig.extract_parameters` method now extracts and returns only parameters that can be found in the `parameters` dictionary instead of including known, but missing, parameters with a default value `None`. This prevents overwriting API-specific parameters that are specified only in the configuration in subsequent stages of workflows. This also has the effect of ensuring that the `eFetch` of the `PubMed` workflow correctly sends record IDs that we wish to retrieve data for.

### Developer Notes:
- Added a Makefile for easier discovery and automation of package development tasks and workflows (install, test, lint, format, help, shell, spell_checker, docs).
- Added `CLAUDE.md` and `.github/AI_ASSISTED_PROMPTS.md` to support automated code review, analysis of potential security risks/breaking changes, and scans for test coverage. The CLAUDE.md essentially gives large language models a tailored intro into the package and directs resources where beneficial, and the `.github/AI_ASSISTED_PROMPTS.md` provides a curated set of prompt templates to support development. While primarily intended for code review, any edits should always follow core philosophy mentioned in the `CONTRIBUTING.md`: Understand what you commit.
- Added a `CITATION.cff` and a `README.md` citation section for researchers who use or may use `ScholarFlux` in their work.
- Updated the `tox.ini` and `.github/workflows/ci.yml` to explicitly run the full test suite on Python 3.14 (in addition to Python versions 3.10+). These two files are used to define the continuous integration github workflow tests ('ci.yml') and the steps required for testing, linting, and determining test coverage (`tox.ini`)
- Restructured the flow of the README.md into (more) logical subsections and added a direct `Table of Contents` section while renaming the previous `Table of Contents` section to `Quick Links`. Also added a caveat to the `README.md` and the `caching_strategies.rst` to advise that users check the TOS of each provider before implementing cache for downstream use. The `NOTICE` file now states explicitly that contributors and authors claim no liability for misuse and violations of the terms of service of an API provider.

## [0.3.1] - 12/13/2025
**Note** While this patch is marked as a minor version bump, this patch brings substantial improvements and production hardening with changes that are also backward compatible with previous versions. Existing codebases will not require modification to benefit from this patch.

### Added
- **API-Specific Parameters** Each provider now supports a greater range of API-specific parameters that are directly related to sorting and filtering. As APIs often grow and change, this patch attempts to support the highest value parameters directly while changes to supported API parameters can easily be extended using `APIParameterConfig.add_parameters` for modifications to provider-config logic for the current session. The logic for parameter validation was also extended to allow for basic parameter validation before requests are sent to catch obvious errors with helpful error messages that indicate the parameter value, provider, and field that needs revision. Use `SearchAPI.describe()` for more information on the default parameters that are accepted for the current provider configuration.
- Created a `BaseAPIParameterMap.add_parameter()` method for more efficiently extending parameter maps with custom API-specific parameters at runtime.
- **Production Quality Examples** Created 3 extensive examples showing how ScholarFlux can be integrated in AI/ML pipelines and workflows. The first implements a basic, scheduled pipeline for the retrieval of new articles within a specific date range. The orchestrated pipeline illustrates how searches can be scheduled and how processed records can be deduplicated and written to a parquet on the daily retrieval of new records. The second uses modern patterns to illustrate how ML embeddings can be used to search for papers relevant to a specific topic. The third uses PydanticAI with ScholarFlux to illustrate how scholar-flux can be integrated in agentic frameworks to classify works relevant to a specific topic. The creation of the documentation for each step was partially assisted with Anthropic's Claude and is therefore (very) verbose. Make sure to be familiar with each provider's terms of use before embarking on a project using AI and use appropriate citations!
- The `SearchCoordinator` now defines `last_response` as a class-level property. It now delegates last-response retrieval to a new implementation, `ResponseHistoryRegistry`, that stores the last received response by provider. Because this registry is thread-safe and is automatically used to retrieve the last response from a provider independent of the query with direct applications to threaded query retrieval.
- **API Configuration Options**: Added `SCHOLAR_FLUX_DEFAULT_USER_AGENT` and `SCHOLAR_FLUX_DEFAULT_MAILTO` environment variable support. On the creation of a session object, the `BaseAPI` and the `SearchAPI` clients, by extension, can automatically read these variables from the operating system environment to use a user-specified defaults for smarter session creation. Defining `SCHOLAR_FLUX_DEFAULT_USER_AGENT` allows end-users to default to the specified User-Agent when not explicitly specified during session creation.
- The `SearchAPIConfig` instance that validates the parameters passed to the `SearchAPI` on creation now supports the automatic reading of a `SCHOLAR_FLUX_DEFAULT_MAILTO` environment variable for the `Crossref` and `OpenAlex` providers when a direct `mailto` variable is not explicitly specified. 
- **Caching Configuration**: Caching mechanisms can now be directly controlled using the `SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND` environment variable for session-based caching and the `SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE` environment variable for response processing cache. These options are opt-in and control the type of cache backend that is used when enabled.
- Implemented the `ConfigLoader.get` method to streamline checks for available environment variables within the OS environment when not explicitly defined in the `config_settings.config` dictionary.
- Added comprehensive test coverage for retry logic with minimum delays, user agent configuration from environment variables, and implicit wait behavior during retries.

### Changed
- **Rate Limiting Enhancements**: Added `wait_since()` method to support waiting based on reference timestamps, improved thread safety with reentrant locks, and added `sleep()` method for direct interval control. The `RateLimiter.rate()` now modifies the interval used in all subsequent calls to the rate limiter for the duration of the context.
- **Retry delay calculation**: The `RetryHandler.calculate_retry_delay()` method now computes delays as `min_retry_delay + min(backoff_factor * (2^attempt), max_backoff)` instead of just exponential backoff. This ensures a baseline delay even on the first retry.
- **Threaded Rate Limiter Improvements**: The `ThreadedRateLimiter` is enhanced to use reentrant locks where beneficial to improve concurrency in future applications.
- The `RetryHandler.execute_with_retry()` method now accepts optional `min_retry_delay`, `backoff_factor`, and `max_backoff` parameters for per-request retry configuration. This is especially useful when tuning retry-delays with maximum backoffs for special cases where requests need dynamic rate limiting.
- The `RetryHandler` now allows users to specify a `min_retry_delay` parameter that affects the minimum time waited in between requests when the `RetryHandler` is used in isolation. This feature is directly integrated into the `SearchCoordinator` to fine-tune adaptive rate-limiting when remote API internal server errors occur.
- **OpenAlex rate limiting**: Reduced default `request_delay` from 6 seconds to 1 second to better align with OpenAlex's documented rate limits. When the `mailto` parameter is used, the rate limit for the `polite pool` rises to 10 requests per second, and is highly recommended as a result.
- **Improved RetryHandler Integration**: `SearchCoordinator` now automatically initializes its `RetryHandler` with `min_retry_delay` set to the API's `request_delay` and `backoff_factor` adjusted to `min(request_delay * 0.25, 0.5)` for more predictable retry behavior that respects provider rate limits. The `RetryHandler` can directly make use of both custom and threaded `sleep` integrations by accepting an optional `sleep_func`.
- The `SearchCoordinator.robust_request()` method now passes `min_retry_delay` and `backoff_factor` to `RetryHandler.execute_with_retry()`, allowing dynamic override based on `request_delay` parameter.
- Unified configuration access: Internal code paths now use `config_settings.get()` instead of direct `config_settings.config.get()` access. This change provides cleaner fallback to environment variables while maintaining backward compatibility (direct dict access still works).
- `SessionManager` now reads the default user agent from `SCHOLAR_FLUX_DEFAULT_USER_AGENT` environment variable if no user agent is provided during initialization.

### Documentation
- **Expanded Quick Start section**: Added "Simplest Example" subsection showing minimal usage for immediate results.
- **Enhanced Getting Started**: Added Prerequisites, Provider Access, and Developer Installation subsections with clear setup instructions.
- **Improved Feature Documentation**: Added "Features at a Glance" summary with bullet points for quick reference and detailed rate limit documentation for all providers.
- **Better Code Examples**: Updated `main.py` and README examples with improved comments, normalization patterns, and comprehensive error handling demonstrations.

## 0.3.0 - 12/03/2025
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
