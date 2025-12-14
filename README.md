![ScholarFluxBanner](assets/Banner.png)

[![codecov](https://codecov.io/gh/sammieh21/scholar-flux/graph/badge.svg?token=D06ZSHP5GF)](https://codecov.io/gh/sammieh21/scholar-flux)
[![CI](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml)
[![CodeQL](https://github.com/SammieH21/scholar-flux/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/github-code-scanning/codeql)
[![Documentation Status](https://readthedocs.org/projects/mypy/badge/?version=latest)](https://mypy.readthedocs.io/en/latest/?badge=latest)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

[![Beta](https://img.shields.io/badge/status-beta-yellow.svg)](https://github.com/SammieH21/scholar-flux)
[![mypy: Type Checked](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)



## Table of Contents

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

- Manually coordinating rate limits across providers (6s for PLOS, 4s for arXiv, 1s for Crossref...)
- Writing custom parsers for XML (PubMed, arXiv) and JSON (Crossref, OpenAlex) responses
- Mapping **75+ inconsistent field names** across 8 providers (`title` vs `article_title` vs `headline`)
- Implementing retry logic with exponential backoff for transient failures
- Building caching layers to avoid redundant requests
- Handling provider-specific pagination quirks and knowing when to stop requesting
- Managing multi-step workflows (PubMed's search → fetch process)

**Result**: Weeks of integration work just to retrieve data consistently.

### The Solution

ScholarFlux handles that complexity through:

- **🚀 Concurrent Thread Orchestration**: Query multiple providers simultaneously with shared rate limiters
- **📡 Streaming Results**: Generator-based architecture for memory-efficient large-scale retrieval
- **🎯 Schema Normalization**: Automatic transformation of provider-specific fields into universal academic schema
- **🗄️ Two-Tier Caching**: HTTP response caching + processed result caching with production backends
- **🛡️ Security-First**: Automatic credential masking and optional encrypted caching

### Features at a Glance

- **Rate limiting** - Automatically respects per-provider rate limits to avoid getting banned
- **Two-layer caching** - Optionally caches successful requests and response processing to avoid redundant requests
- **Security-first** - Identifies and masks sensitive data (API keys, emails, credentials) before they appear in logs
- **Request preparation** - Configures provider-specific API parameters and settings for data retrieval
- **Response validation** - Verifies response structure before attempting to process data
- **Record processing** - Prepares, logs, and returns intermediate data steps and final processed results
- **Concurrent orchestration** - Retrieves data from multiple APIs concurrently with multithreading
- **Intelligent halting** - After unsuccessful requests, knows when to retry or halt multi-page retrieval

### Performance: Real-World Impact

**Scenario**: Retrieve 1,250 records from 5 providers (PLOS, arXiv, Core API, OpenAlex, Crossref)

| Method | Time | Speedup |
|--------|------|---------|
| Sequential requests | ~19 min | Baseline |
| ScholarFlux concurrent threading | ~6 min | **3x faster** |

**Why?** ScholarFlux uses concurrent threads with shared rate limiters. While PLOS thread waits 6s for rate limiting, arXiv (4s), Core API (~6s), OpenAlex (1s), and Crossref (1s) threads query simultaneously. The more providers you query, the greater the optimization.

## Focus

- **Unified Access**: Aggregate searches across multiple academic databases and publishers
- **Rich Metadata Retrieval**: Fetch detailed metadata for each publication, including authors, publication date, abstracts, and more
- **Advanced Search Capabilities**: Support both simple searches and provider-specific, complex query structures to filter by publication date, authorship, and keywords
- **Open Access Integration**: Prioritize and query open-access resources (for use within the terms of service for each provider)
- **Production-Ready Architecture**: Built with dependency injection, comprehensive error handling, and type safety for deployment in production environments

## Installation

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) for dependency management (for development)
- An API key depending on the API Service Provider (may be available through your academic institution or by registering directly with the provider)

### Provider Access

While some APIs may require an API key, the majority of providers do not. **OpenAlex, PLOS, Crossref, and arXiv work out-of-the-box** and seamlessly for both single-page and multi-page/provider retrieval, even with the default settings.

APIs such as PubMed, CORE, and Springer Nature do, however, provide API access without payment or subscription for uses within the terms of service.

All sources have rate limits that users should abide by to prevent `Too Many Requests` status codes when requesting data. Luckily, **ScholarFlux handles this part automatically for you**!

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

# For encrypted session caching
pip install scholar-flux[cryptography]
```

## Quick Start

### Simplest Example

Just want to see it work? Here's the absolute minimum:

```python
from scholar_flux import SearchCoordinator

coordinator = SearchCoordinator(query="machine learning", provider_name="arxiv")
result = coordinator.search_page(page=1)

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

# Create a coordinator for a single provider
coordinator = SearchCoordinator(query="machine learning", provider_name="arxiv")

# Search and get results:
response = coordinator.search_page(page=1)

print(response)
# OUTPUT: SearchResult(query='machine learning', provider_name='arxiv', page=1, response_result=ProcessedResponse(...))

if response:
    # show the total number of records that were retrieved and process
    print(f"Found {response.total_query_hits} total results for the query, {response.query}")
    print(f"Retrieved {response.record_count} records from page {response.page}")

    # Access processed data with predictable fields:
    for article in response.normalize():
        abstract = article.get('abstract')
        summary = abstract[:80] + '...' if abstract else 'Not Found'

        print(f"Title: {article.get('title')}")
        print(f"Authors: {article.get('authors')}")
        print(f"Abstract: {summary}")
else:
    print(f"Oops, An error occurred during response retrieval for page {response.page}: ", response.error, response.message)
```

## 🔬 Origin Story

Initially developed during a 4-year CDC Public Health Analyst Fellowship as an exploratory project investigating how AI and ML could enhance research workflows. The challenge: aggregating data from multiple academic databases for ML-driven research, where each provider has different APIs, rate limits, and response formats.

Early prototypes of these AI/ML-driven workflows revealed that reliable data integration was critical—without consistent, validated data from heterogeneous sources, downstream analysis fails.

Built and presented at CDC meetings as a solution for AI-assisted systematic literature review and meta-analysis workflows. The initial demonstration showcased a Springer Nature integration with embedding-based similarity search to find related articles and abstracts—illustrating how unified API access could power ML-driven research discovery.

After the fellowship, I recognized the broader need beyond public health research and open-sourced it, expanding from the initial Springer Nature integration to 7+ providers with comprehensive documentation and production-ready features.

**Technical foundation:**
- **~45,000 lines of code**: ~27,000 LOC source + ~18,000 LOC comprehensive tests
- **96% test coverage**: Rigorous testing across all functionality and edge cases
- **Security-focused**: Automated CVE scanning, credential masking, encrypted caching
- **Type-safe**: mypy strict mode throughout entire codebase
- **Production-ready architecture**: Dependency injection, comprehensive error handling, horizontal scaling support

## 📚 Comprehensive Documentation

ScholarFlux includes **8 detailed tutorials** and **3 AI/ML example pipelines** covering everything from basic setup to production deployment:

### Core Tutorials
- **Getting Started** - Installation, first search, environment configuration
- **Response Handling Patterns** - Error handling, metadata extraction, pagination control
- **Multi-Provider Search** - Concurrent orchestration, streaming results, shared rate limiters
- **Schema Normalization** - Building ML-ready datasets with consistent fields across providers

### Advanced Topics
- **Caching Strategies** - Redis, MongoDB, SQLAlchemy for production-scale deployments
- **Advanced Workflows** - Multi-step retrieval patterns, PubMed workflow internals
- **Custom Providers** - Extending ScholarFlux to new APIs with custom configurations
- **Production Deployment** - Docker, monitoring, encrypted caching, and security essentials

### Example Pipelines
- **Retrieval Pipeline Orchestration** - Scheduled data preparation with Parquet export
- **Semantic Similarity Search** - Embedding-based paper discovery with ModernBERT
- **Agentic Literature Review** - LLM-powered classification with PydanticAI

Each tutorial includes working code examples and real-world use cases. The documentation depth reflects the package's maturity and production-readiness.


## Architecture

ScholarFlux is built around three core components that work together through dependency injection:

```
SearchCoordinator
├── SearchAPI (HTTP retrieval + rate limiting)
│   ├── RateLimiter (thread-safe rate limiting with Retry-After support)
│   ├── RetryHandler (exponential backoff with configurable limits)
│   ├── Session (requests or requests-cache)
│   ├── APIParameterMap (provider-specific parameter translation)
│   ├── SensitiveDataMasker (masks sensitive data before logging)
│   └── SearchAPIConfig (records per page, request delays, provider URL/name, API keys)
│
└── ResponseCoordinator (processing pipeline)
    ├── DataParser (XML/JSON/YAML → dict)
    ├── DataExtractor (dict → records list)
    ├── DataProcessor (records transformation with filtering)
    ├── ResponseMetadataMap (pagination metadata extraction - v0.3.0)
    └── DataCacheManager (processed result storage)
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
- **DataCacheManager**: Manages caching backends (In-Memory, Redis, MongoDB, SQLAlchemy)
- **RateLimiter**: Enforces per-provider rate limits with proactive `Retry-After` detection *(v0.3.0)*
- **RetryHandler**: Implements exponential backoff with case-insensitive header parsing *(v0.3.0)*

### How Concurrent Orchestration Works

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
multi = MultiSearchCoordinator()
multi.add_coordinators([plos, arxiv, crossref])
results = multi.search_pages(pages=pages)  # multithreading=True by default

# What happens:
# t=0s: All threads request the first page simultaneously
# t=~0.5s: All responses received → rate limiters activate
# t=6-7s: PLOS completes (slowest, determines total time)
# Total: ~6-7 seconds (bottlenecked by slowest provider)
# Speedup: Approximately 2x faster than sequential (~6s vs ~12s)
```

This optimization compounds with multiple pages. For 10 pages across 4 providers, the speedup grows to **3x faster** than sequential retrieval.



### Multi-Provider Search with Normalization

```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator
import pandas as pd

# Create coordinators for multiple providers
providers = ['crossref', 'arxiv', 'pubmed', 'plos']
# [Modify this] Helps to identify the origin of the request (You)
user_agent='MyResearchProject/1.0 (mailto:your.email@institution.edu)'
coordinators = [
    SearchCoordinator(query="CRISPR gene editing", provider_name=provider, user_agent=user_agent)
    for provider in providers
]

# Coordinate concurrent searches
multi = MultiSearchCoordinator()
multi.add_coordinators(coordinators)

# Search pages 1-10 across all providers simultaneously
results = multi.search_pages(pages=range(1, 11))

# Filter successful results and normalize to common schema
df = pd.DataFrame(results.filter().normalize())

# Unified dataset with consistent field names across providers
print(df[['provider_name', 'title', 'doi', 'year']].head())
```


## Core Features

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
- **CORE**: 6 seconds between requests (token-based, not request-based)
- **Springer Nature**: 2 seconds between requests

**Override the default delay:**
```python
# PLOS default is 6 seconds, override to 2 seconds
response = coordinator.search(page=1, request_delay=2.0)
```

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

For custom field mappings and advanced normalization, see the [Schema Normalization Tutorial](https://SammieH21.github.io/scholar-flux/schema_normalization.html).

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

### Response Validation & Error Handling

ScholarFlux validates responses at multiple stages and provides three distinct response types:

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


## Supported Providers

ScholarFlux includes pre-configured support for these academic databases:

| Provider | Search | Normalization | Special Features |
|----------|--------|---------------|------------------|
| **arXiv** | ✅ | ✅ | Preprints, categories |
| **Crossref** | ✅ | ✅ | DOI metadata, funding |
| **CORE** | ✅ | ✅ | Open access aggregator |
| **OpenAlex** | ✅ | ✅ | Comprehensive metadata |
| **PLOS** | ✅ | ✅ | Open access biology |
| **PubMed** | ✅ | ✅ | Two-step workflow (search → fetch) |
| **Springer Nature** | ✅ | ✅ | Requires API key |

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
| **Type safety** (mypy strict) | ✅ | ⚠️ Partial | ⚠️ Partial | ⚠️ Partial | ❌ |

### Real-World Scenario

**Without ScholarFlux** (using individual packages):
```python
# Researcher needs data from 4 sources
from habanero import Crossref
import arxiv
from pymed import PubMed

# Manual threading implementation
# Manual rate limiting for each provider
# Manual schema normalization across 75+ field variations
# Manual caching layer for both requests and results
# Manual error handling with retry logic
# Manual workflow orchestration for PubMed's two-step process
# Result: 200+ lines of boilerplate code
```

**With ScholarFlux**:
```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator
import pandas as pd

# Automatic concurrent execution with rate limiting
coordinators = [
    SearchCoordinator(query="CRISPR", provider_name='crossref'),
    SearchCoordinator(query="CRISPR", provider_name='arxiv'),
    SearchCoordinator(query="CRISPR", provider_name='pubmed'),
    SearchCoordinator(query="CRISPR", provider_name='plos')
]

multi = MultiSearchCoordinator()
multi.add_coordinators(coordinators)
results = multi.search_pages(pages=range(1, 10))

# Automatic normalization with fallback field paths
df = pd.DataFrame(results.filter().normalize())

# Metadata-driven pagination intelligence
for result in results:
    print(f"{result.provider_name}: {result.total_query_hits} total results")

# Result: 12 lines, production-ready
```

### What ScholarFlux Adds

1. **Concurrent Orchestration**: Query 7+ providers simultaneously—**3x faster** than sequential
2. **Metadata-Driven Intelligence**: Extract pagination metadata for precise control
3. **Resilient Schema Normalization**: Normalize **75+ provider-specific fields** with fallback paths
4. **Proactive Rate Limiting**: Prevent 429 errors by reading `Retry-After` headers
5. **Production Infrastructure**: Redis/MongoDB/SQL caching, credential masking, comprehensive error handling
6. **Workflow Automation**: Multi-step APIs handled transparently with metadata preservation
7. **Memory Efficiency**: Stream results as they arrive—process page 1 while fetching page 100

### When to Use Each Approach

**Use provider-specific packages** (`habanero`, `arxiv`, `pybliometrics`) when:
- ✅ You need **one database** with provider-specific advanced features
- ✅ You want **fine-grained control** over provider-specific parameters
- ✅ You're building **provider-specific workflows** not covered by ScholarFlux

**Use ScholarFlux** when:
- ✅ You need **3+ databases** queried concurrently
- ✅ You need **consistent schemas** for ML/analytics pipelines
- ✅ You need **production reliability** with comprehensive error handling
- ✅ You need **metadata-driven pagination** that knows when to stop
- ✅ You need **resilient field mapping** that handles API inconsistencies
- ✅ You're building **production systems** requiring caching and horizontal scaling
- ✅ You want **rapid prototyping** without orchestration boilerplate

**Complementary use**: ScholarFlux can be extended to wrap existing packages for providers it doesn't support natively. See the [Custom Provider Tutorial](https://SammieH21.github.io/scholar-flux/custom_providers.html).

For detailed comparison, see the [documentation](https://SammieH21.github.io/scholar-flux/).

## What's New in v0.3.1

v0.3.1 delivers **AI/ML pipeline examples**, **API parameter enhancements**,  and **configuration enhancements** that make ScholarFlux easier to integrate into research workflows.

### 🤖 New AI/ML Pipeline Examples

Three production-ready examples demonstrating ScholarFlux integration with modern AI/ML workflows:

- **[Retrieval Pipeline Orchestration](examples/retrieval_pipeline_orchestration.py)** — Scheduled data preparation pipeline with date filtering, incremental accumulation, and Parquet export. Includes optional daily scheduling via `schedule` or cron.

- **[Semantic Similarity Search](examples/ml_springer_nature_embeddings_similarity.py)** — Combines ScholarFlux with ModernBERT embeddings to discover interdisciplinary research. Searches Springer Nature and ranks papers by semantic similarity to target topics.

- **[Agentic Literature Review](examples/agentic_literature_review.py)** — Multi-provider search with LLM-powered classification using PydanticAI. Demonstrates how to build automated literature review pipelines with structured AI output.

### ⚡ Rate Limiting Improvements
- **OpenAlex optimization**: Reduced default `request_delay` from 6s to 1s to align with documented rate limits. Using the `mailto` parameter enables 10 requests/second via the "polite pool."
- **Thread-safe response history**: New `ResponseHistoryRegistry` tracks last responses per provider across threads, enabling smarter rate limit coordination for concurrent queries.

### 🔧 Configuration Enhancements
- **New environment variables**: `SCHOLAR_FLUX_DEFAULT_USER_AGENT`, `SCHOLAR_FLUX_DEFAULT_MAILTO`, `SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND`, and `SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE` allow setting defaults without code changes. Useful for containerized deployments.
- **Unified config access**: Use `config_settings.get()` and `config_settings.set()` for cleaner configuration with automatic environment variable fallback.
### Retry Logic Improvements
- **Configurable minimum retry delay**: `RetryHandler` now respects `min_retry_delay` parameter for more predictable backoff
- **Smarter backoff calculation**: Retry delays now use `min_retry_delay + exponential_backoff` instead of just exponential backoff
- **SearchCoordinator integration**: Automatically sets `min_retry_delay` based on `request_delay` for consistent rate limiting behavior

### Documentation Enhancements
- **Expanded Quick Start**: Added "Simplest Example" section for immediate usage
- **Improved Getting Started**: Added Prerequisites, Provider Access, and Developer Installation sections
- **Enhanced Feature Documentation**: Added "Features at a Glance" summary and detailed rate limit documentation

### API-Specific Parameters
Each provider now supports sorting, filtering, and provider-native options directly in searches:
```python
# OpenAlex with sorting and filtering
coordinator = SearchCoordinator(query="sunspots", provider_name="openalex")
results = coordinator.search_pages(range(1, 5), sort="cited_by_count:desc", filter="publication_year:2024")

# Crossref with polite pool access
coordinator = SearchCoordinator(query="neural networks", provider_name="crossref")
results = coordinator.search_pages(range(1, 3), sort="published", order="desc", mailto="you@institution.edu")
```

Use `SearchAPI.describe()` to see available parameters for any provider.


These refinements build on v0.3.0's production hardening, making ScholarFlux more reliable and easier to integrate into AI/ML research pipelines.

## What's New in v0.3.0

v0.3.0 focuses on **production hardening** and **edge case reliability**—refining existing orchestration capabilities to handle real-world API variability more robustly.

### Enhanced Pagination Intelligence
ScholarFlux's existing pagination logic now extracts precise metadata from API responses:

```python
response = coordinator.search(page=1)

# Previous: Stopped when len(records) < expected (heuristic)
# Now: Uses provider-reported metadata for precision
print(response.total_query_hits)    # 15,847 (reported by API)
print(response.records_per_page)    # 25 (reported by API)

# Stops at exactly page 634 (15,847 ÷ 25)
# No more false stops from partial pages or rate limit throttling
```

The new `ResponseMetadataMap` standardizes metadata extraction and processing across provider-specific field names (`numFound` for PLOS, `count` for OpenAlex, `total-results` for Crossref).

### Resilient Field Mapping
Enhanced field mapping system supports fallback paths for API response variability:

```python
from scholar_flux.api.normalization import AcademicFieldMap

field_map = AcademicFieldMap(
    provider_name="pubmed",
    # Handles variability: some records have .#text, others don't
    title=["MedlineCitation.Article.ArticleTitle.#text", 
           "MedlineCitation.Article.ArticleTitle"],
    abstract=["MedlineCitation.Article.Abstract.AbstractText.#text",
              "MedlineCitation.Article.Abstract.AbstractText"]
)

# Automatically tries each path until finding data
records = response.normalize(field_map=field_map)
```

### Proactive Rate Limiting
Rate limiter now reads `Retry-After` headers proactively:

```python
# Previous: Request → 429 error → exponential backoff → retry
# Enhanced: Request → Response has "Retry-After: 5" → wait 5s → next request

coordinator.search(page=1)  # Response includes Retry-After header
coordinator.search(page=2)  # Automatically waits before requesting
```

Works with numeric delays and HTTP date formats, with case-insensitive header extraction.

### Non-Paginated Endpoint Support
New `parameter_search()` extends orchestration to custom endpoints:

```python
# Query specialized endpoints (recommendations, cited articles, etc.)
result = coordinator.parameter_search(
    endpoint="/articles/recommend",  # mock endpoint
    article_id="PMC1234567",  # mock ID parameter
    limit=20,  # mock page-limit parameter
    from_request_cache=True
)
# Rate limiting, retry logic, caching, and processing still apply
```

### Complete v0.3.0 Improvements
- **Metadata extraction**: `ResponseMetadataMap` for precise pagination across all providers
- **Resilient normalization**: Fallback field paths handle API response variability  
- **Proactive rate limiting**: Case-insensitive `Retry-After` header detection
- **Non-paginated support**: `parameter_search()` for custom endpoints and workflows
- **Workflow refinement**: PubMed metadata preservation across search steps
- **Session backends**: Auto-configured Redis/MongoDB for production deployments
- **Documentation**: 8 comprehensive Sphinx tutorials

See the [full changelog](https://github.com/SammieH21/scholar-flux/blob/main/CHANGELOG.md) for detailed technical changes.


## Documentation

**Comprehensive tutorials and API reference**: https://SammieH21.github.io/scholar-flux/

### 📚 Core Tutorials

- **[Getting Started](https://SammieH21.github.io/scholar-flux/getting_started.html)** - Installation through first search
- **[Response Handling Patterns](https://SammieH21.github.io/scholar-flux/response_handling_patterns.html)** - Error handling, metadata extraction, pagination control
- **[Multi-Provider Search](https://SammieH21.github.io/scholar-flux/multi_provider_search.html)** - Concurrent orchestration and streaming results
- **[Schema Normalization](https://SammieH21.github.io/scholar-flux/schema_normalization.html)** - Building ML-ready datasets with fallback field mapping

### 🔧 Advanced Topics

- **[Caching Strategies](https://SammieH21.github.io/scholar-flux/caching_strategies.html)** - Two-tier caching with Redis, MongoDB, SQLAlchemy
- **[Advanced Workflows](https://SammieH21.github.io/scholar-flux/advanced_workflows.html)** - Multi-step retrieval, custom pipelines, PubMed workflow internals
- **[Custom Providers](https://SammieH21.github.io/scholar-flux/custom_providers.html)** - Extending ScholarFlux to new APIs with custom metadata maps
- **[Production Deployment](https://SammieH21.github.io/scholar-flux/production_deployment.html)** - Docker, monitoring, encrypted caching, and security essentials

### 🧪 Example Pipelines

Production-quality example templates demonstrating how ScholarFlux can be integrated with AI/ML and data orchestration pipelines. These provide well-tested starting points that can be adapted for production deployments.

- **[Retrieval Pipeline Orchestration](examples/retrieval_pipeline_orchestration.py)** - Scheduled data preparation with date filtering, deduplication, and Parquet export
- **[Semantic Similarity Search](examples/ml_springer_nature_embeddings_similarity.py)** - Embedding-based interdisciplinary paper discovery with ModernBERT
- **[Agentic Literature Review](examples/agentic_literature_review.py)** - Multi-provider search with LLM classification via PydanticAI


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
poetry install --with dev --with tests --all-extras
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


## Contact

Questions or suggestions? Open an issue or email scholar.flux@gmail.com.

---

## 📈 Project Statistics

- **~45,000 Lines of Code** - ~27,000 LOC source + ~18,000 LOC comprehensive tests
- **96% Test Coverage** - Rigorous testing across all functionality and edge cases
- **7 Default Providers** - Pre-configured with schema normalization and metadata extraction
- **Type-Safe Architecture** - mypy strict mode, comprehensive type hints throughout
- **Security-Audited** - Automated CVE scanning via CodeQL and Safety CLI, credential masking
- **Zero Known CVEs** - Continuous security monitoring in CI/CD pipeline
- **8 Comprehensive Tutorials** - Detailed documentation from basics through production deployment
- **3 AI/ML Example Pipelines** - Production-ready examples for embeddings, agents, and scheduled retrieval
- **Stable Beta** (v0.3.1) - Production-ready core with comprehensive test coverage. API refinements in progress toward v1.0 stabilization.

---

**Built with ❤️ for researchers, data engineers, and ML practitioners—the analytical pioneers of the future**
