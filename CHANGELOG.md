# Changelog

All notable changes to scholar-flux will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
