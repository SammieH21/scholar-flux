# CLAUDE.md

This file provides Claude Code (claude.ai/code) with quick-reference context for ScholarFlux development. For complete information, consult the linked documentation which serves as the authoritative source.

### Last updated 5/31/2026 (**v0.6.0**)

> **Note:** This is a quick reference for AI coding assistants working with ScholarFlux.
> For complete, authoritative information, consult:
> - [README.md](README.md) (overview, features, quickstart)
> - [CONTRIBUTING.md](CONTRIBUTING.md) (development guidelines)
> - [Published docs](https://SammieH21.github.io/scholar-flux/) (comprehensive tutorials and API reference)
> - [Local generated docs](docs/build/html/index.html) (if available in your repo checkout)

## Project Overview

ScholarFlux is a production-grade orchestration infrastructure for academic APIs enabling concurrent multi-provider search with automatic rate limiting and schema normalization across 7+ scholarly databases (Python 3.10+ required).

**Full details**: [README.md](README.md)

## Basic Usage

```python
from scholar_flux import SearchCoordinator

# Fill in the user agent to help APIs identify where the request is coming from
user_agent = None  #'MyResearchProject/1.0 (mailto:your.email@institution.edu)'

# Searching for academic records with arXiv... (query and provider are constructor args)
coordinator = SearchCoordinator(
    query="machine learning",
    provider_name="arxiv",  # Normalized under the hood, not case sensitive
    user_agent=user_agent,
    use_cache=True,  # For caching requests
)

result = coordinator.search_page(page=1)

if result:  # Truthy on success (When the `SearchResult` contains a `ProcessedResponse`)
    print(f"Found {result.total_query_hits} total, retrieved {result.record_count}")

    # Processed records containing provider-specific field names
    processed_records = result.data or []

    for record in processed_records:
        print(record.get("title"))

    # Normalized records (unified schema: title, authors, doi, abstract, year, etc.)
    for record in result.normalize():
        print(record["title"], record["year"], record["authors"])
else:  # Falsy on errors (When the `SearchResult` contains `ErrorResponse` or `NonResponse`)
    # Indicates that an error occurred that prevented response retrieval or successful record processing
    print(f"Retrieval unsuccessful ({result.error}): {result.message}")

# View the class-level history of all requests/retry attempts and delays between requests during the current session
# Note: sensitive data is masked by default (e.g., API keys, tokens, `mailto` fields)
print(coordinator.api.rate_limiter.history.structure())
print(coordinator.retry_handler.history.structure())
```

**Search Methods:**
- `coordinator.search_pages(pages=range(1, 3))` — Multi-page Retrieval
- `coordinator.iter_pages(pages=range(1, 3))` — Generator based multi-page retrieval
- `coordinator.parameter_search(endpoint="/", **params)` — Non-paginated endpoint queries
- `coordinator.search_records(min_records=50)` — Auto-calculates pages required

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
├────── ResponseValidator (Defines the logic used to verify response type and structure)
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
| `scholar_flux.sessions`     | Session factories (cached/uncached, encryption, api key auth)       | [Guidelines](CONTRIBUTING.md#scholar_fluxsessions)     |
| `scholar_flux.utils`        | Config loading, helpers, JSON processing, settings/repr utils  | [Guidelines](CONTRIBUTING.md#scholar_fluxutils)        |

## Response Types

Three response types with truthiness semantics for safe error checking. For most use cases, simply check `if result:` to determine success:
- `ProcessedResponse` - **Truthy**: successful retrieval and processing (`True` during an `if result` check)
- `ErrorResponse` - **Falsy**: response received but processing failed (`False` during an `if result` check)
- `NonResponse` - **Falsy**: failed to retrieve API response (`False` during an `if result` check)

| Field                | ProcessedResponse                        | ErrorResponse / NonResponse               |
| -------------------- | ---------------------------------------- | ----------------------------------------- |
| `response`           | Attribute (Response[-like] Object)       | Attribute (Response[-like] Object / None) |
| `metadata`           | Attribute (Extracted response metadata)  | Property (None)                           |
| `cached`             | Property (boolean / None)                | Property (boolean / None)                 |
| `retrieval_timestamp`| Property (datetime / None)               | Property (datetime / None)                |
| `extracted_records`  | Attribute (Records before processing)    | Property (None)                           |
| `processed_records`  | Attribute (Records after processing)     | Property (None)                           |
| `data`               | Property (Alias for `processed_records`) | Property (None)                           |
| `normalize()`        | Returns normalized records               | No-Op (returns None)                      |
| `normalized_records` | Attribute (Records after normalization)  | Property (None)                           |
| `error`              | Property (None)                          | Error type/exception                      |
| `message`            | Optional context                         | Error description                         |

**Note**: When calling `SearchCoordinator.search_page()`, these three response types are nested in a `SearchResult` container that additionally include search metadata annotations (i.e., `query`, `page`, and `provider_name`, `display_name`, `retrieval_timestamp`, `cached`) and references each of the above components through properties or methods. Normalized records can additionally include search metadata annotations via the `include` parameter (i.e., `result.normalize(include={'query', 'page', 'display_name'})`).

**Multi-page results:** the `SearchResultList` exposes `.data`, `.processed_records`, `.normalized_records` as convenience properties for flattened record access across pages, queries, and providers.


The `SearchCoordinator` is designed to orchestrate the full pipeline: parse → extract → process → optionally normalize. To retrieve raw responses without processing, use `SearchCoordinator.fetch()` or `SearchAPI.search()` directly instead.

## Provider Rate Limits

Rate limits are enforced automatically per provider and are used alongside dynamic retry handling for successive failed responses.
**For current values and override instructions, see:** [README.md#rate-limiting](README.md#rate-limiting)

## Adding a New Provider

1. Create a `ProviderConfig` in `src/scholar_flux/api/providers/{provider}.py`
2. Optionally add field map in `src/scholar_flux/api/normalization/{provider}_field_map.py`
3. If the ProviderConfig is valid (uses pydantic for validation), it is automatically imported from `scholar_flux.api.providers` at runtime
4. Add tests with mocked responses in `tests/api/` and `tests/normalize/`

**Detailed guide**: [Custom Providers Tutorial](https://SammieH21.github.io/scholar-flux/custom_providers.html)

## Core Environment Variables

```bash
# API Keys (see Getting Started docs)
SPRINGER_NATURE_API_KEY                       # Required
PUBMED_API_KEY, CORE_API_KEY                  # Optional
CROSSREF_API_KEY                              # Optional (aliases CROSSREF-PLUS-API-TOKEN)

# Package Environment Setup
SCHOLAR_FLUX_HOME                             # Default location for storing .env, cache directories, logs
SCHOLAR_FLUX_LOAD_ENV                         # Whether the default .env is loaded on package initialization

# Logging
SCHOLAR_FLUX_ENABLE_LOGGING=TRUE              # Opt-in (warnings only by default)
SCHOLAR_FLUX_LOG_LEVEL=DEBUG

# Cache Backend & Database Auth (see production_deployment docs)
SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND    # sqlite (default), redis, mongodb, memory, filesystem
SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE   # memory (default), redis, sql, mongodb, null
SCHOLAR_FLUX_MONGODB_HOST, _PORT, _USERNAME, _PASSWORD, _DATABASE, _COLLECTION
SCHOLAR_FLUX_REDIS_HOST, _PORT, _USERNAME, _PASSWORD

# Session Encryption (see SECURITY.md)
SCHOLAR_FLUX_USE_SESSION_CACHE_ENCRYPTION     # Enables encrypted session cache
SCHOLAR_FLUX_CACHE_SECRET_KEY                 # 32-byte URL-safe base64 secret
```

**Guides**: [Getting Started](https://SammieH21.github.io/scholar-flux/getting_started.html) | [Production Deployment](https://SammieH21.github.io/scholar-flux/production_deployment.html) | [Security](https://github.com/SammieH21/scholar-flux/blob/main/SECURITY.md)

## AI-Assisted Development

For AI-assisted code review prompts (test gap analysis, breaking changes, type hints), see [.github/AI_REVIEW_PROMPTS.md](.github/AI_REVIEW_PROMPTS.md).

**Important**: Code generated with AI must be understood, tested, and refactored to match project patterns before committing. See [CONTRIBUTING.md](CONTRIBUTING.md#our-philosophy) for the full philosophy.

---

## Key Terms

Quick definitions for terms used throughout ScholarFlux documentation:

| Term                       | Definition                                                                                                                                                                                                                                           |
| -------------------------- | -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Truthy/Falsy**           | Python objects that evaluate to `True` or `False` in boolean context (e.g., `if/else` conditional logic). Because successful search results are truthy and errors are falsy, `if result:` works intuitively.                                         |
| **Provider**               | An academic database or API (e.g., arXiv, PubMed, Crossref) that ScholarFlux can query.                                                                                                                                                              |
| **Normalization**          | A Record processing method that converts provider-specific field names and formats into a unified schema (e.g., `authors`, `title`, `year`) for consistent downstream processing.                                                                    |
| **MultiSearchCoordinator** | A class composed of multiple `SearchCoordinator` instances that allows for the orchestration of concurrent page searches by provider. Although APIs require rate limiting, searches to other APIs can be coordinated concurrently during wait times. |
| **SearchCoordinator**      | The core class of ScholarFlux that orchestrates single/multi-page API response retrieval, record processing, and caching via the `SearchAPI` and `ResponseCoordinator`.                                                                              |
| **SearchAPI**              | The API client that is responsible for sending paginated, rate-limited requests to a provider based on its accepted parameters and configured rate limits.                                                                                           |
| **ResponseCoordinator**    | Processes API responses through a structured pipeline that parses, extracts records/metadata, and caches processed records via dependency injection.                                                                                                 |
| **Response Types**         | `ProcessedResponse` (success), `ErrorResponse` (processing failed), `NonResponse` (retrieval failed)—each with different truthiness.                                                                                                                 |
| **Response-Like**          | Object that implements core attributes, properties, or methods common to responses (`url`, `status`, `headers`, `content`, and `raise_for_status`). Checked by comparing against a `ResponseProtocol`.                                               |
| **Rate Limiting**          | Enforcing delays between API requests to avoid being blocked by providers. ScholarFlux handles this automatically per provider.                                                                                                                      |
| **RetryHandler**           | A configurable class used by the SearchCoordinator to handle automatic retries with rate limiting/exponential backoff on failed requests while respecting `Retry-After` headers from APIs.                                                           |
| **Field Map**              | A configuration that maps provider-specific field names to normalized schema fields, with optional fallback paths.                                                                                                                                   |
| **Two-Tier Caching**       | Layer 1 (`session cache`) caches raw HTTP responses; Layer 2 (`Response processing cache`) caches records that are extracted/processed from raw responses. Cached searches are returned almost instantly.                                            |
| **Workflow**               | A multi-step workflow used by the `SearchCoordinator` to customize how `search()` and `search_page()` retrieves and processes records. While optional for all other providers, this is required for PubMed's search → fetch pattern.                 |
| **Backoff**                | Progressively increasing delays between retry attempts after failed requests.                                                                                                                                                                        |


---

## Code Standards

- **Type hints**: Required on all functions. Verified with `mypy` strict mode
- **Docstrings**: Required, Google style, coverage checked via `docstr-coverage`
- **Line length**: 120 characters max
- **Testing**: `pytest`: fixtures in `tests/fixtures/` and `tests/conftest.py`
- **Formatting**: `ruff` + `black`
- **Python**: 3.10+ required

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

**Full standards**: [CONTRIBUTING.md#code-style-guidelines](CONTRIBUTING.md#code-style-guidelines)

