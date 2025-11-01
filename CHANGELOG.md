# Changelog

All notable changes to scholar-flux will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
