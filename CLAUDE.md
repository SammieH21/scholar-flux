# CLAUDE.md

This file provides Claude Code (claude.ai/code) with quick-reference context for ScholarFlux development. For complete information, consult the linked documentation which serves as the authoritative source.

### Last updated 1/16/2026 (**v0.4.0**)

> **Note:** This is a quick reference for AI coding assistants working with ScholarFlux.
> For complete, authoritative information, consult:
> - [README.md](README.md) (overview, features, quickstart)
> - [CONTRIBUTING.md](CONTRIBUTING.md) (development guidelines)
> - [Published docs](https://SammieH21.github.io/scholar-flux/) (comprehensive tutorials and API reference)
> - [Local generated docs](docs/build/html/index.html) (if available in your repo checkout)

## Project Overview

ScholarFlux is a production-grade orchestration infrastructure for academic APIs enabling concurrent multi-provider search with automatic rate limiting and schema normalization across 7+ scholarly databases.

**Full details**: [README.md](README.md)

## Basic Usage

```python
from scholar_flux import SearchCoordinator

# Fill in the user agent to help APIs identify where the request is coming from
user_agent= None #'MyResearchProject/1.0 (mailto:your.email@institution.edu)'

# Searching for academic records with arXiv... (query and provider are constructor args)
coordinator = SearchCoordinator(
    query="machine learning",
    provider_name="arxiv", # Normalized under the hood, not case sensitive
    user_agent=user_agent,
    use_cache=True, # For caching requests
    )

result = coordinator.search_page(page=1)

if result:  # Truthy on success
    print(f"Found {result.total_query_hits} total, retrieved {result.record_count}")

    # Processed records containing provider-specific field names
    processed_records = result.data or []

    for record in processed_records:
        print(record.get("title"))

    # Normalized records (unified schema: title, authors, doi, abstract, year, etc.)
    for record in result.normalize():
        print(record["title"], record["year"], record["authors"])
else:
    # Indicates that an error occurred that prevented response retrieval or successful record processing
    print(f"Retrieval unsuccessful ({result.error}): {result.message}")

# View the class-level history of all requests/retry attempts and delays between requests during the current session
# Note: sensitive data  is masked by default (e.g., api keys, tokens, `mailto` fields)
print(coordinator.api.rate_limiter.history.structure())
print(coordinator.retry_handler.history.structure())


```

**Multi-page retrieval:** `coordinator.search_pages(pages=range(1, 5))`
**Multi-provider:** Use `MultiSearchCoordinator` with concurrent threading
**See:** [README.md](README.md#-quick-start) for complete examples

## Development Commands

```bash
# Setup
poetry install --all-extras --with dev,testing,docs

# Testing
poetry run pytest tests -rsx -vv                                 # Executes with the Python version used by Poetry
poetry run pytest tests/api/test_search_coordinator.py -rsx -vv  # Tests a single file
poetry run tox                                                   # Tests all supported Python versions
poetry run tox -e coverage                                       # Runs the test suite with coverage reporting

# Linting
poetry run tox -e lint                      # All checks (mypy, ruff, docstr-coverage)
poetry run mypy src tests                   # Quick Type Checking
poetry run docstr-coverage src              # Checking 100% docstring coverage for source code
poetry run ruff check --fix src tests       # Auto-fix
```

**Complete guide**: [CONTRIBUTING.md](CONTRIBUTING.md#quick-start)

## Simplified Architecture Quick Reference

```
SearchCoordinator
├── SearchAPI (HTTP retrieval + rate limiting)
│   ├── RateLimiter (thread-safe rate limiting with Retry-After support)
│   ├── Session (requests or requests-cache)
│   ├── APIParameterMap (provider-specific parameter translation)
│   ├── SensitiveDataMasker (masks sensitive data before logging)
│   └── SearchAPIConfig (records per page, request delays, provider URL/name, API keys)
│
├─── ResponseCoordinator (processing pipeline)
│   ├── DataParser (XML/JSON/YAML → dict)
│   ├── DataExtractor (dict → records list)
│   ├── DataProcessor (records transformation with filtering)
│   ├── ResponseMetadataMap (pagination metadata extraction - v0.3.0)
│   └── DataCacheManager (In-Memory, Redis, MongoDB, SQLAlchemy, or DuckDB Storage Cache Devices)
├────── RetryHandler (exponential backoff with configurable limits)
├────── ResponseValidator (Defines the logic used to verify context integrity)
└────── SearchWorkflow (Optional provider-specific workflow for multi-step, paginated searches)
```

**Detailed architecture**: [README.md#architecture](README.md#architecture) | [CONTRIBUTING.md](CONTRIBUTING.md#module-specific-guidelines)

## Key Modules

| Module                      | Purpose                                               | Details                                                |
|-----------------------------|-------------------------------------------------------|--------------------------------------------------------|
| `scholar_flux.api`          | Coordination, providers, rate limiting, normalization | [Guidelines](CONTRIBUTING.md#scholar_fluxapi)          |
| `scholar_flux.data`         | Parsers, extractors, processors                       | [Guidelines](CONTRIBUTING.md#scholar_fluxdata)         |
| `scholar_flux.data_storage` | Cache backends (SQL, Redis, MongoDB, Memory, DuckDB)  | [Guidelines](CONTRIBUTING.md#scholar_fluxdata_storage) |
| `scholar_flux.security`     | Credential masking via `SensitiveDataMasker`          | [Guidelines](CONTRIBUTING.md#scholar_fluxsecurity)     |
| `scholar_flux.sessions`     | Session factories (cached/uncached, encryption)       | [Guidelines](CONTRIBUTING.md#scholar_fluxsessions)     |
| `scholar_flux.utils`        | Config loading, helpers, JSON processing, repr utils  | [Guidelines](CONTRIBUTING.md#scholar_fluxutils)        |

## Response Types

Three response types with truthiness semantics for safe error checking:
- `ProcessedResponse` - **Truthy**: successful retrieval and processing
- `ErrorResponse` - **Falsy**: response received but processing failed
- `NonResponse` - **Falsy**: failed to retrieve API response

| Field                | ProcessedResponse                        | ErrorResponse / NonResponse      |
|----------------------|------------------------------------------|----------------------------------|
| `response`           | Attribute (Response-like)                | Attribute (Response-like) / None |
| `metadata`           | Attribute (Extracted response metadata)  | Property (None)                  |
| `extracted_records`  | Attribute (Records before processing)    | Property (None)                  |
| `processed_records`  | Attribute (Records after processing)     | Property (None)                  |
| `data`               | Property (Alias for `processed_records`) | Property (None)                  |
| `normalize()`        | Returns normalized records               | No-op (returns None)             |
| `normalized_records` | Attribute (Records after normalization)  | Property (None)                  |
| `error`              | Property (None)                          | Error type/exception             |
| `message`            | Optional context                         | Error description                |

**Note**: For raw responses without processing, use `SearchAPI.search()` directly. `SearchCoordinator` is for the full pipeline: parse → extract → process → optionally normalize.

## Code Standards

- **Type hints**: Required on all functions (mypy strict mode)
- **Docstrings**: Required, Google style, 100% coverage via docstr-coverage
- **Line length**: 120 characters max
- **Testing**: `requests-mock` for API mocking, fixtures in `tests/fixtures/` and `tests/conftest.py`

**Full standards**: [CONTRIBUTING.md#code-style-guidelines](CONTRIBUTING.md#code-style-guidelines)

## Provider Rate Limits

Rate limits are enforced automatically per provider and are used alongside dynamic retry handling for successive failed responses.
**For current values and override instructions, see:** [README.md#rate-limiting](README.md#rate-limiting)

## Adding a New Provider

1. Create a `ProviderConfig` in `src/scholar_flux/api/providers/{provider}.py`
2. Optionally add field map in `src/scholar_flux/api/normalization/{provider}_field_map.py`
3. If the ProviderConfig is valid (uses pydantic for validation), configurations are automatically imported from `scholar_flux.api.providers` at runtime
4. Add tests with mocked responses in `tests/api/` and `tests/normalize/`

**Detailed guide**: [Custom Providers Tutorial](https://SammieH21.github.io/scholar-flux/custom_providers.html)

## Environment Variables

```bash
# Optional API keys (tests use mocks by default)
PUBMED_API_KEY, SPRINGER_NATURE_API_KEY, CORE_API_KEY

# Logging
SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
SCHOLAR_FLUX_LOG_LEVEL=DEBUG
```

**Full configuration**: [CONTRIBUTING.md#enabling-debug-logging](CONTRIBUTING.md#enabling-debug-logging)

## AI-Assisted Development

For AI-assisted code review prompts (test gap analysis, breaking changes, type hints), see [.github/AI_REVIEW_PROMPTS.md](.github/AI_REVIEW_PROMPTS.md).

**Important**: Code generated with AI must be understood, tested, and refactored to match project patterns before committing. See [CONTRIBUTING.md](CONTRIBUTING.md#our-philosophy) for the full philosophy.
