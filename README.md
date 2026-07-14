![ScholarFluxBanner](assets/Banner.png)

[![codecov](https://codecov.io/gh/sammieh21/scholar-flux/graph/badge.svg?token=D06ZSHP5GF)](https://codecov.io/gh/sammieh21/scholar-flux)
[![CI](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml)
[![CodeQL](https://github.com/SammieH21/scholar-flux/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/github-code-scanning/codeql)
[![Documentation Status](https://github.com/SammieH21/scholar-flux/actions/workflows/docs.yml/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/docs.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

![PyPI - Version](https://img.shields.io/pypi/v/scholar-flux)
[![Beta](https://img.shields.io/badge/status-beta-yellow.svg)](https://github.com/SammieH21/scholar-flux)
[![mypy: Type Checked](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)



## Table of Contents

- [Overview](#overview)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Origin Story](#origin-story)
- [Architecture](#architecture)
- [Core Features](#core-features)
- [Supported Providers](#supported-providers)
- [Comparison with Existing Tools](#comparison-with-existing-tools)
- [What's New in v0.6.0](#whats-new-in-v060)
- [What's New in v0.5.0](#whats-new-in-v050)
- [Documentation](#-documentation)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contact](#contact)

**Quick Links:**
- **Home**: https://github.com/SammieH21/scholar-flux
- **Documentation**: https://SammieH21.github.io/scholar-flux/
- **Source Code**: https://github.com/SammieH21/scholar-flux/tree/main/src/scholar_flux
- **Contributing**: https://github.com/SammieH21/scholar-flux/blob/main/CONTRIBUTING.md
- **Code Of Conduct**: https://github.com/SammieH21/scholar-flux/blob/main/CODE_OF_CONDUCT.md
- **Issues**: https://github.com/SammieH21/scholar-flux/issues
- **Security**: https://github.com/SammieH21/scholar-flux/blob/main/SECURITY.md


## Overview

ScholarFlux is production-grade orchestration infrastructure for academic APIs, initially developed during a **4-year CDC public health analysis fellowship** to address the challenges researchers face when aggregating data across multiple scholarly databases. It enables **concurrent multi-provider search with automatic rate limiting, streaming result delivery, and intelligent schema normalization** across 7+ scholarly databases—arXiv, PubMed, Springer Nature, Crossref, OpenAlex, PLOS, and CORE.

Query multiple academic databases simultaneously while ScholarFlux handles provider-specific quirks, rate limits, response validation, and format inconsistencies—delivering ML-ready datasets with consistent schemas.

### The Problem

Academic research requires querying multiple databases, but each provider implements their own parameter names, pagination mechanisms, rate limits, error conditions, and response formats. Building integrations with multiple academic APIs typically means:

- Manually coordinating rate limits across providers (6s for PLOS, 10s per batch request for CORE, 4s for arXiv...)
- Writing custom parsers for XML (PubMed, arXiv) and JSON (Crossref, OpenAlex) responses
- Mapping inconsistent field names and data types across separate APIs and databases
- Implementing retry logic that handles connection errors, internal server errors, client-side errors
- Building caching layers to avoid redundant requests
- Handling provider-specific pagination quirks and knowing when to stop requesting
- Managing API tokens and sensitive fields securely and efficiently
- Handling provider-specific workflows required to retrieve records effectively (PubMed)

**Result**: Weeks of integration work just to retrieve data consistently.

### The Solution

ScholarFlux handles and abstracts away the complexity of retrieving and processing data from Academic APIs through provider-specific rate limiting, concurrent thread orchestration, streaming result delivery, automatic schema normalization, two-tier caching with production backends (Redis, MongoDB, SQLAlchemy, DuckDB), and security-first credential masking. The result: **~3x faster** multi-provider retrieval with consistent, ML-ready output. The architecture handles rate limiting coordination, response validation, and intelligent retry logic automatically.


### Who Is This For?

- **Researchers** conducting systematic literature reviews and meta-analyses across databases
- **Data Engineers** building academic pipelines requiring reliable retrieval, caching, request throttling with robust error handling
- **ML Practitioners** requiring consistently structured, ML-ready datasets with preprocessed fields

### Features at a Glance

- **Security-first** - Identifies and masks sensitive data (API keys, emails, credentials) before they appear in logs
- **Rate limiting** - Automatically respects per-provider rate limits to avoid getting banned
- **Request preparation** - Configures provider-specific API parameters and settings for data retrieval
- **Intelligent halting** - After unsuccessful requests, knows when to retry or halt multi-page retrieval
- **Response validation** - Verifies response structure before attempting to process data
- **Concurrent orchestration** - Retrieves data from multiple APIs concurrently with multithreading
- **Record processing** - Prepares, logs, and returns intermediate data steps and final processed results
- **API-Aware Normalization** - Consolidates API-specific record structures into a unified, ML/analytics-ready schema
- **Two-layer caching** - Optionally caches successful requests and response processing to avoid redundant requests

### Focus

- **Unified Access**: Aggregate searches across multiple academic databases and publishers
- **Rich Metadata Retrieval**: Fetch detailed metadata for each publication, including authors, publication date, abstracts, and more
- **Advanced Search Capabilities**: Support both simple searches and provider-specific, complex query structures to filter by publication date, authorship, and keywords
- **Open Access Integration**: Prioritize and query open-access resources (for use within the terms of service for each provider)
- **Production-Ready Architecture**: Built with dependency injection, comprehensive error handling, and type safety for deployment in production environments

## 📦 Installation

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) for dependency management (for development)
- An API key depending on the API Service Provider (may be available through your academic institution or by registering directly with the provider)

### Provider Access

While some APIs may require an API key, the majority of providers do not. **OpenAlex, PLOS, Crossref, CORE, and arXiv work out-of-the-box** and seamlessly for both single-page and multi-page/provider retrieval, even with the default settings.

APIs such as Springer Nature, while requiring API keys, provide API access without payment or subscription for uses within the terms of service. PubMed and the CORE API, while not requiring API keys, greatly increase the allowable requests per second with an API key.

All sources have rate limits that users should abide by to prevent `Too Many Requests` status codes. ScholarFlux handles rate limiting automatically.

### Basic Installation

```bash
pip install scholar-flux
```

This installs the core package with minimal dependencies for JSON-based providers (PLOS, OpenAlex, Crossref).

### Installation with Extras

```bash
# For XML parsing (PubMed, arXiv workflows)
pip install scholar-flux[parsing]

# For production caching (Redis, MongoDB, SQLAlchemy)
pip install scholar-flux[database]

# For DuckDB support (embedded analytical database)
pip install scholar-flux[duckdb]

# For encrypted session caching
pip install scholar-flux[cryptography]
```

### Configuration (Optional)

ScholarFlux works out of the box, but environment variables enable higher rate limits and cleaner deployments:

```bash
# Identify your application (recommended for API providers)
export SCHOLAR_FLUX_DEFAULT_USER_AGENT="MyApp/1.0 (mailto:you@institution.edu)"

# Enable "polite pool" access for Crossref/OpenAlex (10x higher rate limits)
export SCHOLAR_FLUX_DEFAULT_MAILTO=your.email@institution.edu

# Centralize config, cache, and logs (recommended for Docker/production)
export SCHOLAR_FLUX_HOME=/opt/scholar-flux

# Default cache backends (optional - memory/sqlite used otherwise)
export SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND=redis      # HTTP response cache
export SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE=redis     # Processed result cache
```

If the User-Agent is not set, the `requests` library will use its default when sending requests (e.g., `python-requests/2.32.5`). While the default user-agent may be accepted, rate limits may be lower for certain APIs as a result.

For production deployments with Redis/MongoDB, API keys, and Docker configuration, see the [Production Deployment Guide](https://SammieH21.github.io/scholar-flux/production_deployment.html).

## 🚀 Quick Start

### Simplest Example

Just want to see it work? Here's the absolute minimum:

```python
from scholar_flux import SearchCoordinator

coordinator = SearchCoordinator(query="machine learning", provider_name="arxiv")
result = coordinator.search_page(1)

if result:
    print(f"Success! Got {result.record_count} records")

    # Note: result.data might be empty if the query matches no documents
    if result.data:
        print(f"Title of first article: {result.data[0].get('title')}")
    else:
        print("Query returned no results. Try a different search term.")
else:
    print(f"Error: {result.error}")
```

### Complete Example

For real-world usage with normalization and error handling:

```python
from scholar_flux import SearchCoordinator
from scholar_flux.utils import JsonFileUtils
from datetime import date
from pathlib import Path

# Create a coordinator for a single provider
coordinator = SearchCoordinator(query="machine learning", provider_name="arxiv")

# Search and get results:
page = 1
response = coordinator.search_page(page=page)

print(response)
# OUTPUT: SearchResult(query='machine learning', provider_name='arxiv', page=1, response_result=ProcessedResponse(...))

if response:
    # show the total number of records that were retrieved and processed
    print(f"Found {response.total_query_hits} total results for the query, {response.query}")
    print(f"Retrieved {response.record_count} records from page {response.page}")

    # Access processed data with predictable fields:
    normalized_records = response.normalize()
    for article in normalized_records:
        abstract = article.get('abstract')
        summary = abstract[:80] + '...' if abstract else 'Not Found'

        print(f"Title: {article.get('title')}")
        print(f"Authors: {article.get('authors')}")
        print(f"Abstract: {summary}")

    # Optionally write the result to a JSON file to your documents folder (Note: arXiv is fundamentally open access)
    filename = Path.home() / "Documents" / f"arXiv_ml_page_{page}-{date.today()}.json"
    JsonFileUtils.save_as(normalized_records, filename)
    print(f"Records written to '{filename}'!")
else:
    print(f"Oops, an error occurred during response retrieval for page {response.page}: ", response.error, response.message)
```

## Origin Story

Initially developed during a 4-year CDC Public Health Analyst Fellowship as an exploratory project investigating how AI and ML could enhance research workflows. The challenge: aggregating data from multiple academic databases for ML-driven research, where each provider has different APIs, rate limits, and response formats.

Early prototypes of these AI/ML-driven workflows revealed that reliable data integration was critical—without consistent, validated data from heterogeneous sources, downstream analysis fails.

Built and presented at CDC meetings as a solution for AI-assisted systematic literature review and meta-analysis workflows. The initial demonstration showcased a Springer Nature integration with embedding-based similarity search to find related articles and abstracts—illustrating how unified API access could power ML-driven research discovery.

After the fellowship, I recognized the broader need beyond public health research and open-sourced it, expanding from the initial Springer Nature integration to 7+ providers with comprehensive documentation and production-ready features.

**Technical foundation:**
- **~63,786 lines of code**: ~35,670 LOC source + ~28,116 LOC comprehensive tests
- **98% test coverage**: Rigorous testing across all functionality and edge cases
- **Security-focused**: Automated CVE scanning, credential masking, encrypted caching
- **Type-safe**: Comprehensive mypy type checking throughout the entire codebase
- **Production-ready architecture**: Dependency injection, comprehensive error handling, horizontal scaling

## Architecture

ScholarFlux is built around three core components that work together through dependency injection:

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

### Concurrency Architecture

For multi-provider searches, ScholarFlux uses a sophisticated threading model with shared rate limiters:

```
MultiSearchCoordinator
├── Thread Pool (per-provider threads)
│   ├── Thread 1: PLOS (shared rate limiter across all PLOS queries)
│   │   └── Concurrent: query1_page1, query1_page2, query1_page3 → (waits 6s between)
│   ├── Thread 2: arXiv (shared rate limiter)
│   ├── Thread 3: OpenAlex (shared rate limiter)
│   └── Thread 4: Crossref (shared rate limiter)
│
├── Shared Rate Limiter Registry (cross-query coordination)
└── Generator Pipeline (streaming results via concurrent.futures.as_completed)
```

**Key Design Decisions**:
- **Threading over asyncio**: Simpler for users, better for I/O-bound workloads with rate limits
- **Generator-based streaming**: Memory-efficient, process results incrementally without blocking
- **Shared rate limiters**: Multiple queries to the same provider coordinate through a single `ThreadedRateLimiter`
- **Concurrent execution**: Maximizes throughput by requesting from all providers simultaneously within rate limit constraints

Each component has a specific responsibility:

- **SearchAPI**: Creates HTTP requests and handles provider-specific parameter building
- **ResponseCoordinator**: Orchestrates parsing → extraction → transformation → caching
- **SearchCoordinator**: Delegates between SearchAPI (retrieval) and ResponseCoordinator (processing)

Supporting components include:

- **SensitiveDataMasker**: Pattern matching to identify, mask, and register sensitive strings (API keys, tokens)
- **DataParser**: Parses XML, JSON, and YAML responses into dictionaries
- **DataExtractor**: Extracts records from nested dictionaries with configurable paths
- **DataProcessor**: Transforms records using field mappings and filtering rules
- **ResponseMetadataMap** *(v0.3.0)*: Extracts pagination metadata across provider-specific field names
- **DataCacheManager**: Manages caching backends (In-Memory, Redis, MongoDB, SQLAlchemy, DuckDB)
- **RateLimiter**: Enforces per-provider rate limits with proactive `Retry-After` detection *(v0.3.0)*
- **RetryHandler**: Implements exponential backoff with case-insensitive header parsing *(v0.3.0)*

### How Concurrent Orchestration Works

**Minimal Example**: Retrieving 200 records across 3 providers — 2 pages each

```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator
# ❌ Sequential approach (traditional)
query = "machine learning"
pages = [1, 2]
plos = SearchCoordinator(query=query, provider_name='plos')
crossref = SearchCoordinator(query=query, provider_name='crossref')
arxiv = SearchCoordinator(query=query, provider_name='arxiv') # requires `xmltodict`

results_plos = plos.search_pages(pages)  # Request → waits 6 seconds between requests
results_arxiv = arxiv.search_pages(pages)  # Request → waits 4 seconds between requests
results_crossref = crossref.search_pages(pages)  # Request → waits 1 second between requests

# Total: ~12-13 seconds for 6 requests (the delay between requests plus processing time adds up)

# ✅ ScholarFlux concurrent threading (default)
multi_search_coordinator = MultiSearchCoordinator.from_coordinators([plos, arxiv, crossref])
results = multi_search_coordinator.search_pages(pages=pages)  # multithreading=True by default

# What happens:
# t=0s: All threads request the first page simultaneously
# t=~0.5s: All responses received → rate limiters activate
# t=6-7s: PLOS completes (slowest, determines total time)
# Total: ~6-7 seconds (bottlenecked by slowest provider)
# Speedup: Approximately 2x faster than sequential (~6s vs ~12s)
```

### Performance: Real-World Benchmarks

This optimization compounds with multiple pages and providers:

**Scenario**: Retrieve ~1,650 records across 6 providers (Crossref, PLOS, arXiv, OpenAlex, Springer Nature, PubMed) — 10 pages each

| Method                           | Time       | Speedup          |
|----------------------------------|------------|------------------|
| Sequential requests              | ~2.5 min   | Baseline         |
| ScholarFlux concurrent threading | ~45 sec    | **~3x faster**   |

**Why the speedup?** While one provider waits on rate limits, others continue simultaneously. With varied delays across providers (1s–6s), concurrent execution maximizes throughput.

> **Note on CORE API**: CORE is fully supported but enforces stricter burst limits beyond the documented 10s/request delay. After ~10–13 consecutive requests, you may encounter 429 errors and multi-minute cooldowns. For large CORE queries, consider reducing records per request or spreading retrieval across multiple sessions.



### Multi-Provider Search with Normalization

```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator

# Create coordinators for multiple providers (None of the following require an API key)
providers = ['crossref', 'arxiv', 'openalex', 'plos', 'core']
# Set your own user agent to help APIs identify the origin of the request:
user_agent = None # 'MyResearchProject/1.0 (mailto:your.email@institution.edu)'
coordinators = [
    SearchCoordinator(query="CRISPR gene editing", provider_name=provider, user_agent=user_agent)
    for provider in providers
]

# Coordinate concurrent searches
multi_search_coordinator = MultiSearchCoordinator.from_coordinators(coordinators)

# Use `search_page` to retrieve a single page across several providers
results = multi_search_coordinator.search_page(1)

# Filter successful results and normalize to a common schema, including the formatted provider name
normalized_results = results.filter().normalize(include={'display_name'})
for record in normalized_results[:5]:
    print(f"Title: {record['title']} ({record['year']})")
    print(f"Source: {record['display_name']} ({record['url']})")
    print("-"*100)
```


## Core Features

### Schema Normalization

ScholarFlux normalizes provider-specific field names into a common academic schema:

```python
# Raw records have provider-specific field names
results = coordinator.search_pages(pages=range(1, 5))

# Normalize to universal schema
normalized = results.normalize()

# Now all records have consistent fields:
# 'title', 'doi', 'authors', 'abstract', 'journal', 'year', etc.
df = pd.DataFrame(normalized)
```

Each provider implements API-aware post-processing that transforms raw, nested responses into consistent output:

| Transformation | Raw Value | Normalized Output |
|----------------|-----------|-------------------|
| Year extraction (`PubMed`) | `[[2024, 6, 15]]` | `2024` |
| Author formatting (`Crossref`) | `[{"given": "Jane", "family": "Smith"}]` | `["Jane Smith"]` |
| OA resolution (`Crossref`) | `"creativecommons.org/licenses/by/4.0/"` | `true` |
| Abstract reconstruction (`OpenAlex`) | `{"Hello": [0], "world": [1]}` | `"Hello world"` |

**What normalization handles automatically:**
- **Nested field traversal**: Paths like `MedlineCitation.Article.AuthorList.Author` (PubMed) or `authorships.institutions.display_name` (OpenAlex)
- **Fallback paths**: Variability in record fields is handled by using fallback paths for different record types when the default data location is empty
- **Type conversions**: Dates to ISO format, years as integers, booleans from strings
- **Author formatting**: Nested author dictionaries parsed into normalized name lists across providers
- **Abstract reconstruction**: OpenAlex inverted indexes reconstructed into text; Crossref HTML tags stripped
- **URL reconstruction**: PLOS and PubMed article URLs built from DOI/PMID identifiers
- **Cross-database identifiers**: CORE extracts arXiv ID, PMID, and MAG ID for entity resolution

For custom field mappings and advanced normalization, see the [Schema Normalization Tutorial](https://SammieH21.github.io/scholar-flux/schema_normalization.html).

### Response Validation & Error Handling

ScholarFlux validates responses at multiple stages, gracefully handling and reporting errors when they occur. When timeouts, missing API keys, missing dependencies, and other errors occur, the `SearchCoordinator` gracefully handles and returns error messages via response classes to indicate what went wrong, all the while ensuring that retrieval and processing pipelines across multiple providers aren't brought to a halt.

The client provides three distinct response types:

```python
response = coordinator.search(page=1)

if response:  # Falsy if error or no response
    # ProcessedResponse - successful retrieval and processing
    print(f"Retrieved {len(response.data)} records")
    print(f"Total available: {response.total_query_hits}")
else:
    # ErrorResponse or NonResponse - something went wrong
    print(f"Error: {response.message}")
    print(f"Error type: {response.error}")
```

**Response types:**
- `ProcessedResponse`: Successful retrieval and processing
- `ErrorResponse`: Retrieved response but encountered processing error
- `NonResponse`: Failed to retrieve response (connection error, timeout, etc.)

**Note:** When `coordinator.search_page(page=1)` is used instead (recommended), a `SearchResult` is returned instead for safe field access, wrapping each response type and returning `None` instead of raising errors when attempting to access inapplicable fields or methods on failed requests.

### Rate Limiting

ScholarFlux respects per-provider rate limits automatically:

```python
coordinator = SearchCoordinator(query="sleep", provider_name='plos')

# Each request waits as needed to maintain the rate limit
results = coordinator.search_pages(pages=range(1, 3))
```

**Default Rate Limits:**

ScholarFlux implements conservative rate limits that respect each provider's requirements:

- **PLOS**: 6.1 seconds between requests
- **arXiv**: 4 seconds between requests
- **OpenAlex**: 1 second between requests (conservative—OpenAlex uses 5 metrics)
- **PubMed**: 2 seconds between requests (3 req/sec → 10 req/sec with API key)
- **Crossref**: 1 second between requests
- **CORE API**: 10 seconds between requests (token-based, not request-based)
- **Springer Nature**: 6 seconds between requests

**Override the default delay:**
```python
# Override the default delay for a provider
coordinator = SearchCoordinator(query = 'AI in Academia', provider_name = "arXiv", request_delay=5)
# Or set the delay dynamically during a search
response = coordinator.search(page=1, request_delay=3.1)
```

**Note:** Retry attempts and dynamic throttling are handled at the level of the `RetryHandler` for successive failed requests. If a provider requests a `Retry-After` delay longer than the configured `max_backoff` (default: 120s), ScholarFlux will raise a `RetryAfterDelayExceededException` to prevent indefinite waiting. When this occurs during coordinated searches, an `ErrorResponse` is returned, containing the complete response details for inspection and debugging. You can adjust this behavior by increasing the `max_backoff` or disabling strict enforcement with `RetryHandler.RAISE_ON_DELAY_EXCEEDED = False`. See the [Response Handling Patterns Tutorial](https://SammieH21.github.io/scholar-flux/response_handling_patterns.html) for details.

### Two-Tier Caching

ScholarFlux implements two caching layers:

1. **HTTP Response Caching** (Layer 1): Uses `requests-cache` to cache raw API responses
2. **Processed Result Caching** (Layer 2): Caches extracted and processed records

```python
from scholar_flux import SearchCoordinator, CachedSessionManager, DataCacheManager

# HTTP response caching
session_manager = CachedSessionManager(backend='sqlite', expire_after=3600)
session = session_manager()
processing_cache = DataCacheManager.with_storage('memory')  # or sql/sqlite if SQLAlchemy is available

# Both layers working together
coordinator = SearchCoordinator(
    query="neuroscience",
    provider_name='pubmed',
    session=session,  # Layer 1: HTTP caching
    cache_manager=processing_cache # Layer 2: Response processing cache
)

response = coordinator.search(page=1)  # Fetches from API
response2 = coordinator.search(page=1)  # Instant return from cache
```

For production deployments with Redis or MongoDB, see the [Caching Strategies Tutorial](https://SammieH21.github.io/scholar-flux/caching_strategies.html).

**Note:** ScholarFlux supports in-memory and persistent caching for raw responses and response processing cache for efficiency and rate limiting.
Always review the terms of service for each provider before caching or storing retrieved data.


### API-Specific Parameters

Specific APIs often define custom logic for sorting, filtering, and other provider-native options that can be used for custom searches:

```python
# OpenAlex: Sorting by citation count and filtering by year
coordinator = SearchCoordinator(query="sunspots", provider_name="openalex")
results = coordinator.search_pages(range(1, 5), sort="cited_by_count:desc", filter="publication_year:2024")

# Crossref: Polite pool access for 10x rate limits:
coordinator = SearchCoordinator(query="neural networks", provider_name="crossref")
results = coordinator.search_pages(range(1, 3), sort="published", order="desc", mailto="you@institution.edu")

# Use `.describe()` to see all accepted universal and a minimal, extensible set of API-specific parameters for a provider:
print(coordinator.api.describe())

```

### Workflow Automation

Some providers (like PubMed) require multiple API calls. ScholarFlux handles this automatically:

```python
# This single call executes a two-step workflow automatically:
# 1. PubMedSearch: Get article IDs
# 2. PubMedFetch: Retrieve full articles with abstracts
coordinator = SearchCoordinator(query="neuroscience", provider_name='pubmed')
result = coordinator.search(page=1)

# Complete metadata preserved across workflow steps
print(result.metadata)  # Query info, ID lists, result counts
print(result.data)      # Full article records with abstracts
```

See the [Advanced Workflows Tutorial](https://SammieH21.github.io/scholar-flux/advanced_workflows.html) for custom multi-step workflows.

### Request Observability

Debug rate limiting and retry behavior with built-in history tracking. Both `RateLimiter` and `RetryHandler` maintain the last 1000 recorded events:

```python
from scholar_flux import SearchCoordinator
from scholar_flux.api.rate_limiting import RetryHandler

# Fresh requests and retry attempts recorded in class-level history for easier search observability across APIs.
RetryHandler.history.clear_history()

# Limit history to last 500 records (1000 by default)
RetryHandler.resize_history(500)

# Run a batch of searches
coordinator = SearchCoordinator(query="psychology AND dissonance", provider_name="crossref")
responses = coordinator.search_pages(pages=range(1, 5))

# Inspect retry history to see what happened during the last batch of requests.
for attempt in RetryHandler.history:
    print(f"  URL: {attempt.url}")
    print(f"  Status: {attempt.status_code}, Success: {attempt.success}")
    print(f"  Timestamp: {attempt.timestamp}, Delay: {attempt.delay}")

    if attempt.error:
        print(f" Error: {attempt.error}")
        print(f" Error Message: {attempt.message}")
    print('-' * 105)

# Export the retry history into a list of dictionaries
retry_history = RetryHandler.history.export_history()

# Calculate the success rate across all requests:
if retry_history:
    success_rate = sum(a['success'] for a in retry_history) / len(retry_history)
    print(f"Success rate: {success_rate:.1%}")
```

### Non-Paginated Endpoint Support

Use `parameter_search()` to query specialized endpoints that don't require pagination (recommendations, citations, metadata lookups, full text retrieval):

```python
result = coordinator.parameter_search(
    endpoint="/articles/recommend",  # mock endpoint
    article_id="PMC1234567",  # mock ID parameter
    limit=20  # mock page-limit parameter
)
```

This method is used internally by workflows for multi-step retrieval patterns. See [Advanced Workflows](https://SammieH21.github.io/scholar-flux/advanced_workflows.html) for actual implementations in workflows.


## Supported Providers

ScholarFlux includes pre-configured support for these academic databases:

| Provider            | Search | Normalization | Special Features                   |
| ------------------- | ------ | ------------- | ---------------------------------- |
| **arXiv**           | ✅     | ✅            | Preprints, categories              |
| **Crossref**        | ✅     | ✅            | DOI metadata, funding              |
| **CORE**            | ✅     | ✅            | Open access aggregator             |
| **OpenAlex**        | ✅     | ✅            | Comprehensive metadata             |
| **PLOS**            | ✅     | ✅            | Open access biology                |
| **PubMed**          | ✅     | ✅            | Two-step workflow (search → fetch) |
| **Springer Nature** | ✅     | ✅            | Requires API key                   |

All providers support:
- Automatic rate limiting with proactive `Retry-After` handling
- Two-tier caching (HTTP + processed results)
- Intelligent pagination with metadata extraction
- Schema normalization with fallback field paths
- Comprehensive error handling and retries

For adding custom providers, see the [Custom Provider Tutorial](https://SammieH21.github.io/scholar-flux/custom_providers.html).


## Comparison with Existing Tools

ScholarFlux is **not a replacement** for single-provider clients like `habanero`, `pybliometrics`, or `arxiv`. It's an **orchestration layer** that complements these tools for multi-provider research workflows.

### Architectural Differences

**Existing packages** (`habanero`, `pybliometrics`, `arxiv`, `metapub`, `scholarly`):
- Single-provider API wrappers
- Provider-specific response structures
- Basic or no caching
- Sequential request patterns
- Designed for provider-specific features

**ScholarFlux**:
- Multi-provider orchestration engine
- Unified schema normalization across providers
- Two-tier caching (HTTP + processed results)
- Concurrent threading with shared rate limiters
- Production-ready architecture (Redis, MongoDB, SQLAlchemy)

### Feature Comparison

| Feature | ScholarFlux | habanero | pybliometrics | arxiv | metapub |
|---------|-------------|----------|---------------|-------|---------|
| **Multi-provider concurrent execution** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Shared rate limiter coordination** | ✅ | ❌ | ⚠️ Single provider | ❌ | ⚠️ Single provider |
| **Two-tier caching system** | ✅ | ❌ | ⚠️ Basic file cache | ❌ | ❌ |
| **Cross-provider schema normalization** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Metadata-driven pagination** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Proactive rate limiting** (`Retry-After`) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Resilient field mapping** (fallback paths) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Streaming generator results** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Multi-step workflow automation** | ✅ | ❌ | ❌ | ❌ | ⚠️ PubMed only |
| **Production cache backends** | ✅ Redis, MongoDB, SQL | ❌ | ⚠️ File system | ❌ | ❌ |
| **Security features** (credential masking) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Type safety** (mypy checked) | ✅ | ⚠️ Partial | ⚠️ Partial | ⚠️ Partial | ❌ |

### What ScholarFlux Adds

1. **Concurrent Orchestration**: Query 7+ providers simultaneously—**3x faster** than sequential
2. **Metadata-Driven Intelligence**: Extract pagination metadata for precise control
3. **Resilient Schema Normalization**: Normalize **120 provider-specific fields** with fallback paths
4. **Proactive Rate Limiting**: Prevent 429 errors by reading `Retry-After` headers
5. **Production Infrastructure**: Redis/MongoDB/SQL caching, credential masking, comprehensive error handling
6. **Workflow Automation**: Multi-step APIs handled transparently with metadata preservation
7. **Memory Efficiency**: Stream results as they arrive—process page 1 while fetching page 100

### When to Use Each Approach

**Use provider-specific packages** (`habanero`, `arxiv`, `pybliometrics`) when:
- You need **one database** with provider-specific advanced features
- You want **fine-grained control** over provider-specific parameters
- You're building **provider-specific workflows** not covered by ScholarFlux

**Use ScholarFlux** when:
- You need **3+ databases** queried concurrently
- You need **consistent schemas** for ML/analytics pipelines
- You need **production reliability** with comprehensive error handling
- You need **metadata-driven pagination** that knows when to stop
- You need **resilient field mapping** that handles API inconsistencies
- You're building **production systems** requiring caching and horizontal scaling
- You want **rapid prototyping** without orchestration boilerplate


### Real-World Scenario

**Without ScholarFlux** (using individual packages):
```python
# Researcher needs data from 4 sources
from habanero import Crossref
import arxiv
from pymed import PubMed

# Manual threading implementation
# Manual rate limiting for each provider
# Manual schema normalization across 120 field variations
# Manual caching layer for both requests and results
# Manual error handling with retry logic
# Manual workflow orchestration for PubMed's two-step process
# Result: 200+ lines of boilerplate code
```

**With ScholarFlux**:
```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator
import pandas as pd

# Each coordinator automatically handles parameter mappings and URL structures under the hood:
coordinators = [
    SearchCoordinator(query="CRISPR", provider_name=provider_name, use_cache=True)
    for provider_name in ("crossref", "arxiv", "pubmed", "plos")
]

# Automatic threaded execution with rate limiting
multi_search_coordinator = MultiSearchCoordinator.from_coordinators(coordinators)

# Search pages 1-10 across all providers simultaneously
results = multi_search_coordinator.search_pages(pages=range(1, 11))

# Identify the total number of records retrieved per provider:
for coordinator in multi_search_coordinator.coordinators:
    print(
        f"Total record count for {coordinator.display_name}:",
        results.select(provider_name=coordinator.provider_name).record_count,
    )

# Metadata-driven pagination intelligence
for result in results:
    print(f"{result.display_name} Page {result.page}: {result.record_count} records ({result.total_query_hits:,} hits)")

# Automatic normalization with API-specific post processing. The `include` field adds search-specific fields to the output:
df = pd.DataFrame(
    results.filter().normalize(keep_api_specific_fields=False, include={"query", "page", "provider_name"})
)

# Output columns after record normalization:
print(df.columns)
# ['provider_name', 'doi', 'url', 'record_id', 'title', 'abstract', 'authors', 'journal', 'publisher', 'year', 'date_published',
#  'date_created', 'keywords', 'subjects', 'full_text', 'citation_count', 'open_access', 'license', 'record_type', 'language',
#  'is_retracted', 'query', 'page']

# Result: 14 lines, production-ready
```


**Complementary use**: ScholarFlux can be extended to wrap existing packages for providers it doesn't support natively. See the [Custom Provider Tutorial](https://SammieH21.github.io/scholar-flux/custom_providers.html).

For detailed comparison, see the [documentation](https://SammieH21.github.io/scholar-flux/).

## What's New in v0.6.0

ScholarFlux v0.6.0 brings significant improvements to security, usability, and production hardening, featuring **Cache Authentication Environment Variable Support**, **Session Encryption Environment Default Setup**, **Customizable API Header & Parameter Authentication Support**, and **Convenience Record Accessibility**.

### Cache Authentication Environment Variable Support

Both Redis and MongoDB Session and Response Cache storage backends each support the utilization of environment variables for authentication.

On initialization, connection credentials are read from the environment variables:

- `SCHOLAR_FLUX_REDIS_USERNAME`
- `SCHOLAR_FLUX_REDIS_PASSWORD`
- `SCHOLAR_FLUX_MONGODB_USERNAME`
- `SCHOLAR_FLUX_MONGODB_PASSWORD`

When non-missing values are provided for authentication credentials, these are automatically masked, only unmasking when a connection is performed.

The following workflow summarizes the setup, which only requires modifying .env files or the environment variables:

```python
from scholar_flux import SearchCoordinator, CachedSessionManager, DataCacheManager, config_settings, masker

# Env variables automatically read as secret strings when available:
redis_has_auth = config_settings.get("SCHOLAR_FLUX_REDIS_USERNAME") and config_settings.get("SCHOLAR_FLUX_REDIS_PASSWORD")

# Layer 2 Response Cache: automatically reads host, port, and auth parameters
redis_cache_manager = DataCacheManager.with_storage("redis")

if redis_has_auth:
    print("Authentication parameters for Redis are available. These parameters are automatically applied on response cache initialization")
    # Configuration parameters are read as secrets when available
    assert masker.is_secret(redis_cache_manager.cache_storage.config.get("username"))
    assert masker.is_secret(redis_cache_manager.cache_storage.config.get("password"))

# Verify whether connection initialization was successful
redis_cache_manager.verify_connection()

# Session Cache uses the same configuration settings for initialization:
mongo_has_auth = config_settings.get("SCHOLAR_FLUX_MONGODB_USERNAME") and config_settings.get("SCHOLAR_FLUX_MONGODB_PASSWORD")
session_cache_manager = CachedSessionManager(backend="mongodb")

if mongo_has_auth:
    print("Authentication parameters for MongoDB are available. These parameters are automatically applied on session initialization")
    assert masker.is_secret(session_cache_manager.kwargs.get("username"))
    assert masker.is_secret(session_cache_manager.kwargs.get("password"))

# create a session, verifying connection success
mongodb_session = session_cache_manager(verify_connection=True)

# Initializes as usual:
coordinator = SearchCoordinator(query="Caching and Auth", cache_manager=redis_cache_manager, session=mongodb_session)
results = coordinator.search_page(1)
```


### Session Encryption Environment Default Setup

ScholarFlux v0.6.0 now streamlines session encryption serialization setup to automatically implement encryption when a valid secret key is stored within the OS environment.

```python
from scholar_flux.sessions import CachedSessionManager, EncryptionPipelineFactory
from scholar_flux import config_settings, SearchCoordinator

# Check if a valid encryption key is defined within the environment or configuration settings
if EncryptionPipelineFactory.prepare_secret_key():
    print("A Secret Key exists within the environment")
else:
    print("Creating a new secret key. **Important**: Export the key to your environment to persist it across sessions.")
    secret_key = EncryptionPipelineFactory.generate_secret_key()


    env_var = "SCHOLAR_FLUX_CACHE_SECRET_KEY"
    # persists within the Python session/REPL
    config_settings.set(env_var, secret_key)

    # Write the key to the default location, creating a new .env file with `create=True` if a dedicated file doesn't already exist.
    config_settings.write_key(env_var, create=True, raise_on_error=True)

    ## Uncomment for default encryption setup across Python sessions:
    # config_settings.set("SCHOLAR_FLUX_USE_SESSION_CACHE_ENCRYPTION", True)
    # config_settings.write_key("SCHOLAR_FLUX_USE_SESSION_CACHE_ENCRYPTION")

# Create an encrypted session or raise the error preventing its creation
session = CachedSessionManager.with_session(
    cache_name="encrypted-session-requests",
    backend="sqlite",
    raise_on_error=True,
    use_encryption=True,  # To explicitly override encryption environment variable configuration settings
)
# INFO - Successfully initialized an EncryptionPipeline...
# INFO - Cached session (...) successfully established

coordinator = SearchCoordinator(query="encryption strategies", session=session)

result = coordinator.search_page(page=1)
# SearchResult(query='encryption strategies', provider_name='plos', page=1, ..., display_name='PLOS')


```


### Customizable API Header & Parameter Authentication Support

`SearchAPI.build_auth()` now handles the core facets of parameter vs. header authentication with API keys and tokens under the hood:

```python
from scholar_flux import SearchAPI, config_settings
crossref_api_key = config_settings.get("CROSSREF_API_KEY")  # Either a secret string or None, is read automatically otherwise.
crossref_search_api = SearchAPI(query='example_query', provider_name = "crossref", api_key=crossref_api_key)
# Called under the hood during searches: Adds the Crossref API token to the auth headers to increase rate limits when available:
crossref_search_api.build_auth()
# OUTPUT: AuthAPIKeyHeader(api_key=**********, parameter_name='CROSSREF-PLUS-API-TOKEN', scheme='Bearer')

search_api = SearchAPI(query='example_query', provider_name = "core")
# Check whether the API key for Core is available. Should return an `AuthAPIKeyParameter(SecretKey)` if the API key exists.
search_api.build_auth()
# OUTPUT: AuthAPIKeyParameter(api_key=**********, parameter_name='api_key')
```


### Convenience Record Accessibility Improvements

The `SearchResultList` implements QOL improvements regarding processed record and normalized record retrieval and processing to increase consistency in single and multipage retrieval setups:

```python
from scholar_flux import SearchCoordinator
from scholar_flux.utils import truncate

# Retrieve the first 3 pages and normalize records most relevant to gene editing:
coordinator = SearchCoordinator(query="CRISPR gene editing", provider_name="OpenAlex")
results = coordinator.search_pages(pages=range(1, 4), normalize_records=True)

# Property alias for all processed records across all pages
print(f"Record List Preview: {truncate(results.data, max_length=400)}")

# Display normalized records after post-processing and normalization:
for article in results.normalized_records:  # Flattens previously normalized record lists by default
    print(f"Title: {article['title']}")
    print(f"Authors: {article['authors']}")
    print(f"Year: {article['year']}")
    print(f"Abstract: {truncate(article['abstract'] or 'N/A', max_length = 120)}")
    print("*" * 120)
```

See the [full changelog](https://github.com/SammieH21/scholar-flux/blob/main/CHANGELOG.md) for detailed technical changes.


## What's New in v0.5.0

The v0.5.0 release is designed to increase API maintainability and introduce improved **Cache Initialization and Retrieval Utilities**, **Record Count-Based Retrieval**, and **Search Result Metadata Observability**.

### Session Cache Initialization Improvements

With the aim of making the session setup utility for caching requests consistent with the API for caching processed responses, the `CachedSessionManager` implements a `with_session` helper that allows for the quick and efficient creation of a new `CachedSession`:

The `CachedSessionManager` now also implements connection verification to ensure that Redis and MongoDB cached sessions with invalid connection specifications or unavailable servers fail fast instead of in production when connection verification is enabled on initialization.

```python
from scholar_flux import CachedSessionManager

# For a simple sqlite CachedSession stored in a default `.scholar_flux` directory:
user_agent = None # Your user agent. Example: 'MyResearchProject/1.0 (mailto:your.email@institution.edu)')
session = CachedSessionManager.with_session("sqlite", user_agent = user_agent, cache_name = "project_session_cache.db")

# Setting up a Redis session, calling `validate_cached_session` under the hood to verify the server connection:
session = CachedSessionManager.with_session("redis", verify_connection=True)

# Or simply validating an already created CachedSession:
CachedSessionManager.validate_cached_session(session)
```

### Search by Record Count

The `SearchCoordinator` and `MultiSearchCoordinator` classes now include a `search_records` method designed to translate the total number of records requested into a page-range specific to the SearchCoordinator configuration for a provider.

Different providers may also have different requirements on the maximum number of records that can be retrieved in a single request that could otherwise make multi-page searches variable if not directly configured by the user.

The `SearchCoordinator.search_records` method allows users to search for the minimum number of pages required to reach the desired minimum record count:

```python
from scholar_flux import CachedSessionManager, DataCacheManager, SearchCoordinator

coordinator = SearchCoordinator(
    provider_name="OpenAlex",
    query="AI Literacy",
    records_per_page=50,
    session=CachedSessionManager.with_session("redis"),
    cache_manager=DataCacheManager.with_storage("redis")
    )

# The equivalent of searching for page 1 and page 2 with 50 records per page
results = coordinator.search_records(min_records=100, page_offset=0)

# [SearchResult(query='AI Literacy', provider_name='openalex', page=1, response_result=ProcessedResponse(cache_key='openalex_ai literacy_1_50', ..., display_name='OpenAlex'),
#  SearchResult(query='AI Literacy', provider_name='openalex', page=2, response_result=ProcessedResponse(cache_key='openalex_ai literacy_2_50', ..., display_name='OpenAlex')]

# Pages 3 and 4
results = coordinator.search_records(min_records=100, page_offset=2)
# [SearchResult(query='AI Literacy', provider_name='openalex', page=3, response_result=ProcessedResponse(cache_key='openalex_ai literacy_3_50', ..., display_name='OpenAlex'),
#  SearchResult(query='AI Literacy', provider_name='openalex', page=4, response_result=ProcessedResponse(cache_key='openalex_ai literacy_4_50', ..., display_name='OpenAlex')]
```

This addition is extensible to the `MultiSearchCoordinator`, aiding the retrieval of a consistent record total by provider:

```python
from scholar_flux import CachedSessionManager, DataCacheManager, MultiSearchCoordinator, SearchCoordinator

session_manager = CachedSessionManager(backend="redis")
data_cache_manager = DataCacheManager.with_storage('redis')
coordinators = [SearchCoordinator(provider_name=provider, query="AI Literacy", session=session_manager(), cache_manager=data_cache_manager) for provider in ('OpenAlex', 'PLOS', 'arXiv', 'PubMed')]
multi_search_coordinator = MultiSearchCoordinator.from_coordinators(coordinators)

results = multi_search_coordinator.search_records(min_records=100)

# [SearchResult(query='AI Literacy', provider_name='openalex', page=1, ...),
#  SearchResult(query='AI Literacy', provider_name='openalex', page=2, ...),
#  SearchResult(query='AI Literacy', provider_name='openalex', page=3, ...),
#  SearchResult(query='AI Literacy', provider_name='openalex', page=4, ...),
#  SearchResult(query='AI Literacy', provider_name='plos', page=1, ...),
#  SearchResult(query='AI Literacy', provider_name='plos', page=2, ...),
#  SearchResult(query='AI Literacy', provider_name='arxiv', page=1, ...),
#  SearchResult(query='AI Literacy', provider_name='arxiv', page=2, ...),
#  SearchResult(query='AI Literacy', provider_name='arxiv', page=3, ...),
#  SearchResult(query='AI Literacy', provider_name='arxiv', page=4, ...)]

```

### Response Processing Cache Retrieval Utilities

The `SearchCoordinator` implements redesigned `get_cached_request` and `get_cached_response` methods with the aim of aligning return types with `ProcessedResponse` and `SearchResult` reconstruction functionality. The new `get_cached_search_result` method then uses the updated `get_cached_response` method for `SearchResult` reconstruction from the Layer 2 processing cache when a cached raw response is not directly available.

```python
from scholar_flux import CachedSessionManager, SearchCoordinator

# Using the same persistent cache from the previous example:
session_manager = CachedSessionManager(backend="redis")

coordinator = SearchCoordinator(provider_name="OpenAlex", query="AI Literacy", records_per_page=50, session=session_manager())

# show the cache keys of previously cached OpenAlex responses for `AI Literacy`.
coordinator.get_cached_response_keys()

# ['SFAPI:openalex_ai literacy_4_50',
#  'SFAPI:openalex_ai literacy_2_50',
#  'SFAPI:openalex_ai literacy_3_50',
#  'SFAPI:openalex_ai literacy_1_50']

result = coordinator.get_cached_search_result(page=1)
# SearchResult(query='AI Literacy', provider_name='openalex', page=1, ..., retrieval_timestamp=datetime.datetime(2026, 2, 25, 3, 7, 51, 488000, tzinfo=datetime.timezone.utc), display_name='OpenAlex')

if result:
    print(f"Retrieved page {result.page} ('{result.cache_key}') for {result.display_name} with query '{result.query}'.")
# Retrieved page 1 ('openalex_ai literacy_1_50') for OpenAlex with query 'AI Literacy'.

```

### Search Result Metadata Observability

With the aim of increasing the ease of identification of cached responses and their retrieval time, the `SearchResult` model now promotes the `cached` property into a `pydantic.computed_field` while additionally adding the `retrieval_timestamp` as a `computed_field`. These fields are shown when printing `SearchResult` objects in consoles such as IPython and Jupyter Notebooks, indicating when and where the search result was retrieved. When serializing `SearchResult` objects and normalizing academic records, these fields can additionally be included to enrich results with additional search metadata to indicate the source and age of a record.

```python
from datetime import datetime
from scholar_flux import CachedSessionManager, SearchCoordinator

coordinator = SearchCoordinator(provider_name="arXiv",
    query="AI Literacy",
    session=CachedSessionManager.with_session('sqlite')
)

results = coordinator.search_records(90)

print(results[0])
# SearchResult(query='AI Literacy', provider_name='arxiv', page=1, response_result=ProcessedResponse(cache_key='arxiv_ai literacy_1_25', metadata='{'@xmlns:opensearch': 'http://a9.com...}', data='[{'id': 'http://arxiv.org/abs/2501.0...] (25 items)'), cached=False, retrieval_timestamp=datetime.datetime(2026, 3, 1, 1, 33, 54, 247000, tzinfo=datetime.timezone.utc), display_name='arXiv')

normalized_records = results.normalize(include={"display_name", "page", "query", "cached", "retrieval_timestamp"})
for record in normalized_records:
    retrieved = record['retrieval_timestamp'].strftime("%Y-%m-%d %H:%M")
    source = f"cache" if record['cached'] else f"{record['display_name']}"
    print(f'Retrieved "{record["title"]}" (page {record["page"]}) from {source} (Retrieval time: {retrieved}).')
# Retrieved "Foundations of GenIR" (page 1) from cache (Retrieval time: 2026-03-01 01:46).
# Retrieved "Competing Visions of Ethical AI: A Case Study of OpenAI" (page 1) from cache (Retrieval time: 2026-03-01 01:46).
# Retrieved "AI Literacy in Low-Resource Languages: Insights from creating AI in Yoruba videos" (page 1) from cache (Retrieval time: 2026-03-01 01:46).
# Retrieved "DeBiasMe: De-biasing Human-AI Interactions with Metacognitive AIED (AI in Education) Interventions" (page 1) from cache (Retrieval time: 2026-03-01 01:46).
# ...


```


## 📚 Documentation

**Comprehensive tutorials and API reference**: https://SammieH21.github.io/scholar-flux/

### Core Tutorials

- **[Getting Started](https://SammieH21.github.io/scholar-flux/getting_started.html)** - Installation through first search
- **[Response Handling Patterns](https://SammieH21.github.io/scholar-flux/response_handling_patterns.html)** - Error handling, metadata extraction, pagination control
- **[Multi-Provider Search](https://SammieH21.github.io/scholar-flux/multi_provider_search.html)** - Concurrent orchestration and streaming results
- **[Schema Normalization](https://SammieH21.github.io/scholar-flux/schema_normalization.html)** - Building ML-ready datasets with fallback field mapping

### Advanced Topics

- **[Caching Strategies](https://SammieH21.github.io/scholar-flux/caching_strategies.html)** - Two-tier caching with Redis, MongoDB, SQLAlchemy
- **[Advanced Workflows](https://SammieH21.github.io/scholar-flux/advanced_workflows.html)** - Multi-step retrieval, custom pipelines, PubMed workflow internals
- **[Custom Providers](https://SammieH21.github.io/scholar-flux/custom_providers.html)** - Extending ScholarFlux to new APIs with custom metadata maps
- **[Production Deployment](https://SammieH21.github.io/scholar-flux/production_deployment.html)** - Docker, monitoring, encrypted caching, and security essentials

### Example Pipelines

Production-quality examples demonstrating ScholarFlux integration with AI/ML workflows. These provide well-tested starting points that can be adapted for production deployments.

- **[Retrieval Pipeline Orchestration](examples/retrieval_pipeline_orchestration.py)** — Scheduled data preparation pipeline with date filtering, incremental accumulation, and Parquet export. Includes optional daily scheduling via `schedule` or cron. See also: [Production Deployment](https://SammieH21.github.io/scholar-flux/production_deployment.html)

- **[Semantic Similarity Search](examples/ml_springer_nature_embeddings_similarity.py)** — Combines ScholarFlux with ModernBERT embeddings to discover interdisciplinary research. Searches Springer Nature and ranks papers by semantic similarity to target topics. See also: [Schema Normalization](https://SammieH21.github.io/scholar-flux/schema_normalization.html)

- **[Agentic Literature Review](examples/agentic_literature_review.py)** — Multi-provider search with LLM-powered classification using PydanticAI. Demonstrates how to build automated literature review pipelines with structured AI output. See also: [Multi-Provider Search](https://SammieH21.github.io/scholar-flux/multi_provider_search.html)


## Contributing

We welcome contributions from the research and open-source communities! If you have suggestions for improvements or new features, please fork the repository and submit a pull request. Please refer to our [Contributing Guidelines](CONTRIBUTING.md) for more information.

### Developer Installation

For those who want to contribute or work with the source code:

1. **Clone the repository:**
```bash
git clone https://github.com/SammieH21/scholar-flux.git
cd scholar-flux
```

2. **Install dependencies using Poetry:**
```bash
poetry install
```

3. **Or to download development tools, testing packages, and all extras:**
```bash
poetry install --with dev,testing,docs --all-extras
```

**Areas where contributions are especially valuable:**
- Adding new academic database providers
- Enhancing normalization mappings for existing providers
- Performance optimizations for large-scale retrieval
- Documentation improvements and tutorials
- Bug reports with reproducible examples


## License

This project is licensed under the Apache License 2.0.

[Apache License 2.0 Official Text](http://www.apache.org/licenses/LICENSE-2.0)

See the LICENSE file for the full terms.

### NOTICE

The Apache License 2.0 applies only to the code and gives no rights to the underlying data. Be sure to reference the terms of use for each provider to ensure that your use is within their terms.


## Acknowledgments

Thanks to Springer Nature, Crossref, PLOS, PubMed, arXiv, OpenAlex, and CORE for providing public access to their academic databases through their respective APIs. This project uses Poetry for dependency management and requires Python 3.10 or higher.

Special appreciation to the research software engineering community and the open-source contributors who have helped improve ScholarFlux through bug reports, feature suggestions, and pull requests.


## Citation

If you use ScholarFlux in your research, please cite it:

```bibtex
@software{scholarflux,
  author = {Haskin, Sammie},
  title = {ScholarFlux: Production-Grade Orchestration for Academic APIs},
  year = {2026},
  url = {https://github.com/SammieH21/scholar-flux},
  version = {0.6.1}
}
```

Citing the tools you use helps support open-source development and aids reproducibility.


## Contact

Questions or suggestions? Open an issue or email scholar.flux@gmail.com.

---

## 📊 Project Statistics

- **~63,786 Lines of Code** - ~35,670 LOC source + ~28,116 LOC comprehensive tests
- **98% Test Coverage** - Rigorous testing across all functionality and edge cases
- **7 Default Providers** - Pre-configured with schema normalization and metadata extraction
- **Type-Safe Architecture** - Comprehensive type hints throughout the codebase with mypy strict-mode type checking
- **Security-Audited** - Automated CVE scanning via CodeQL and Safety CLI, credential masking
- **Zero Known CVEs** - Continuous security monitoring in CI/CD pipeline
- **8 Comprehensive Tutorials** - Detailed documentation from basics through production deployment
- **3 AI/ML Example Pipelines** - Production-ready examples for embeddings, agents, and scheduled retrieval
- **Stable Beta** (v0.6.1) - Production-ready core with comprehensive test coverage. API refinements in progress toward v1.0 stabilization.

---

**Built with ❤️ for researchers, data engineers, and ML practitioners—the analytical pioneers of the future**
