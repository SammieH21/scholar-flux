"""Agentic Literature Review with Multi-Provider Academic Search and LLM Classification.

This example demonstrates an advanced ScholarFlux workflow that combines multi-provider
academic search with LLM-powered document classification. It showcases how to build
an automated literature review pipeline that can process thousands of papers across
multiple academic databases.

Workflow Overview
-----------------
1. **Multi-Provider Search**: Query 7 academic APIs simultaneously (Crossref, CORE, PLOS,
   arXiv, OpenAlex, PubMed, Springer Nature) using ScholarFlux's `MultiSearchCoordinator`.

2. **Record Normalization**: Transform heterogeneous API responses into a unified schema
   with consistent field names (title, abstract, doi, authors, etc.).

3. **LLM Classification**: Use a Pydantic AI agent to classify each paper into research
   categories based on its metadata and abstract.

Key Concepts Demonstrated
-------------------------
- `MultiSearchCoordinator`: Orchestrates parallel searches across multiple providers
- `SearchCoordinator`: Manages individual provider search, caching, and processing
- `DataCacheManager`: Persistent caching for processed API responses (Redis/SQL/MongoDB)
- `CachedSessionManager`: HTTP session caching to reduce redundant API calls
- Pydantic AI Agents: Structured LLM output with type-safe classification results

Requirements
------------
- scholar_flux
- pydantic-ai
- Redis server running locally (or switch to SQLite - see configuration section)

Optional (for local LLM inference):
- Ollama with a compatible model (e.g., devstral:24b, mistral, llama3)

LLM Configuration
-----------------
This example supports two LLM backends:

1. **Ollama (Local)** - Default if Ollama is running:
   - Install Ollama: https://ollama.ai
   - Pull a model: `ollama pull devstral:24b-small-2505-q8_0` (or your preferred model)
   - Ensure Ollama is running: `ollama serve`

2. **Anthropic API (Cloud)** - Fallback if Ollama unavailable:
   - Set environment variable: `export ANTHROPIC_API_KEY="your-key-here"`
   - Uses Claude 3.5 Haiku for cost-effective classification

To force a specific backend, modify the `select_model()` function or set:
- `USE_OLLAMA=true` or `USE_OLLAMA=false` as an environment variable

Example Output
--------------
Running this script will:
1. Search 7 providers × 3 queries × 4 pages = up to 84 search result pages
2. Normalize 1000-2000+ records into a unified format
3. Classify a sample of records using the configured LLM
4. Print classification results with rationales

"""

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.providers.ollama import OllamaProvider
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Optional, Literal
from functools import wraps
from random import shuffle
import os

from scholar_flux import DataCacheManager, CachedSessionManager, SearchCoordinator, MultiSearchCoordinator
from scholar_flux.utils import config_settings, generate_repr
from scholar_flux.exceptions import NoRecordsAvailableException
import logging

logger = logging.getLogger("scholar_flux")
logger.setLevel(logging.INFO)
logger.propagate = False
# ============================================================================
# SCHOLARFLUX CONFIGURATION
# ============================================================================
# Configure global settings for API requests. The user agent and mailto are used
# by APIs like Crossref and OpenAlex to identify your application and provide
# faster "polite pool" access.

print("\n" + "=" * 70)
print("SCHOLARFLUX AGENTIC LITERATURE REVIEW")
print("=" * 70)
print("\n[1/6] Configuring ScholarFlux settings...")


# ----
config_settings.set("SCHOLAR_FLUX_DEFAULT_USER_AGENT", "LiteratureResearchProject/1.0:scholar.flux")
# Change this to your email for Crossref and Core for higher rate limits.
# config_settings.set("SCHOLAR_FLUX_DEFAULT_MAILTO", "researcher@university.edu")
# ----


# The 1st layer session cache uses the following variable by default to determine cache backend - change to use a different backend
# Note that the values shown in the type hint are supported by requests_cache under the hood
SESSION_CACHE_BACKEND: Literal["dynamodb", "filesystem", "gridfs", "memory", "mongodb", "redis", "sqlite"] = (
    config_settings.get("SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND") or "sqlite"
)
cached_session_manager = CachedSessionManager(backend=SESSION_CACHE_BACKEND)

# The 2nd layer response cache uses the following variable by default to determine cache backend - change to use a different cache
# Similarly, the type hints for the cache storage are directly supported by the data cache manager
RESPONSE_CACHE_STORAGE: Literal["redis", "sql", "duckdb", "sqlalchemy", "mongodb", "pymongo", "inmemory", "memory", "null"] = (
    config_settings.get("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE") or "inmemory"
)
response_cache_manager = DataCacheManager.with_storage(RESPONSE_CACHE_STORAGE)

# ============================================================================


DEFAULT_PROVIDERS = ["Crossref", "Core", "PLOS", "arXiv", "OpenAlex", "PubMed", "SpringerNature"]
DEFAULT_QUERIES = ["bayesian statistics", "graph based clustering", "statistical innovation"]


def create_coordinators(
    providers: Optional[list[str]] = None, queries: Optional[list[str]] = None
) -> list[SearchCoordinator]:
    """Creates SearchCoordinators for each provider-query combination.

    Each coordinator manages its own search context with shared caching infrastructure. This enables parallel searches
    across providers while maintaining cache efficiency.

    """
    if providers is None:
        providers = DEFAULT_PROVIDERS

    if queries is None:
        queries = DEFAULT_QUERIES

    return [
        SearchCoordinator(
            provider_name=provider,
            query=query,  # search for each default query
            cache_manager=response_cache_manager,  # thread-safe access to redis
            session=cached_session_manager(),  # each should ideally use a separate session
            # processor=RecursiveDataProcessor() # flatten the processed data for easier retrieval
        )
        for provider in providers
        for query in queries
    ]


# ============================================================================
# EXECUTE MULTI-PROVIDER SEARCH
# ============================================================================


print("\n[2/6] Initializing multi-provider search coordinators...")

coordinators = create_coordinators()
multicoordinator = MultiSearchCoordinator()
multicoordinator.add_coordinators(coordinators)
print(multicoordinator)


num_providers = len(DEFAULT_PROVIDERS)
num_queries = len(DEFAULT_QUERIES)
num_coordinators = len(coordinators)

print(f"      ✓ Created {num_coordinators} coordinators ({num_providers} providers × {num_queries} queries)")
print(f"      Providers: {', '.join(DEFAULT_PROVIDERS)}")
print(f"      Queries: {DEFAULT_QUERIES}")

print("\n[3/6] Executing paginated search across all providers...")
print("      This may take a few minutes depending on API response times...")

page_range = range(1, 5)
search_result_list = multicoordinator.search_pages(page_range)

if not search_result_list.record_count:
    err = dedent(
        """
        ✗ ERROR: No records retrieved from any provider.
        Possible causes:
        - Network connectivity issues
        - API rate limiting (try again later)
        - Invalid API keys for authenticated providers
        Halting processing...
        """
    )
    raise NoRecordsAvailableException(err)

print(f"✓ Retrieved {search_result_list.record_count:,} total records")

# ----------------------------------------------------------------------------
# NORMALIZE RECORDS
# ----------------------------------------------------------------------------
# Each API returns data in different formats. The normalize() method transforms
# all records into a consistent schema with standardized field names.
# Note: Some fields may contain nested structures (lists, dicts) for complex metadata.

print("\n[4/6] Normalizing records to unified schema...")

# `filter()` removes failed/empty results, `normalize()` transforms to common schema
# Note: some fields may retrieve nested lists and dictionaries indicating multifaceted fields
normalized_records = search_result_list.filter().normalize()

print(f"      ✓ Normalized {len(normalized_records):,} records")
print("      Fields available: title, abstract, doi, authors, year, keywords, etc.")

# ============================================================================
# DATA MODELS FOR LLM CLASSIFICATION
# ============================================================================
# These dataclasses define the structured output format for the classification agent.
# Using dataclasses with Pydantic AI ensures type-safe, validated LLM responses.


@dataclass
class RecordIdentifiers:
    """Base class providing record identification for classification outputs."""

    id: str
    title: str

    def __repr__(self) -> str:
        """Shows a simple multiline string representation of the current output."""
        return generate_repr(self)


@dataclass
class RecordClassificationOutput(RecordIdentifiers):
    """Successful classification result with category and reasoning.

    The classification field is constrained to a literal type, ensuring the LLM only outputs valid categories. The
    rationale field captures the model's reasoning for interpretability and debugging.

    """

    classification: Literal["bayesian statistics", "graph based clustering", "statistical innovation", "unrelated"]
    rationale: str
    message: Optional[str] = None

    @property
    def error(self) -> None:
        """No-Op field for compatibility with the API."""
        pass


@dataclass
class RecordClassificationError(RecordIdentifiers):
    """Error result when classification fails.

    This class evaluates to False in boolean context, enabling simple error checking:
        result = infer_classification(record)
        if not result:
            print(f"Classification failed: {result.error}")

    """

    error: str
    message: str

    @property
    def classification(self) -> None:
        """No-Op field for compatibility with the API."""
        pass

    @property
    def rationale(self) -> None:
        """No-Op field for compatibility with the API."""
        pass

    def __bool__(self) -> bool:
        """Returns False to indicate that this is an error result."""
        return False


class RecordDataDependencies(BaseModel):
    """Record data structure containing key information on scientific articles, works, and other academic manuscripts.

    This model does not impose strict type restrictions since some fields may greatly differ from the expected type.
    Instead of returning a string, the `url` field may return a list or dictionary of labeled URLs indicating
    particular locations for PDF manuscripts, DOI link, etc.

    The Pydantic AI agent receives this as its `deps` (dependencies), making all fields available for dynamic prompt
    construction.

    Core fields:

    1. The source from which the data was retrieved
    2. Core identifiers (e.g. `doi`, `url`, `record_id`)
    3. Bibliographic metadata ( `title`, `abstract`, `authors`)
    4. Publication metadata (`journal`, `publisher`, `year`, `date_published`, `date_created`)
    5. Content and classification (`keywords`, `subjects`, `full_text`)
    6. Metrics and impact (`citation_count`)
    7. Access and rights (`open_access`, `license`)
    8. Document metadata (`record_type`, `language`)

    """

    # Core identifiers
    provider_name: str
    doi: Any = None
    url: Any = None
    record_id: Any = None

    # Bibliographic metadata
    title: Any = None
    abstract: Any = None
    authors: Any = None

    # Publication metadata
    journal: Any = None
    publisher: Any = None
    year: Any = None
    date_published: Any = None
    date_created: Any = None

    # Content and classification
    keywords: Any = None
    subjects: Any = None
    full_text: Any = None

    # Metrics and impact
    citation_count: Any = None

    # Access and rights
    open_access: Any = None
    license: Any = None

    # Document metadata
    record_type: Any = None
    language: Any = None


# ============================================================================
# LLM MODEL SELECTION AND CONFIGURATION
# ============================================================================
# This section handles automatic model selection with fallback logic.
# Priority: Ollama (local) → Anthropic (cloud)


def check_ollama_available(base_url: str = "http://localhost:11434") -> bool:
    """Check if Ollama server is running and accessible."""
    import urllib.request
    import urllib.error

    try:
        # Ollama exposes a simple endpoint we can ping
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def select_model():
    """Select the best available LLM backend.

    Returns a configured model instance for Pydantic AI.

    To override automatic selection, set the USE_OLLAMA environment variable:
        export USE_OLLAMA=true   # Force Ollama
        export USE_OLLAMA=false  # Force Anthropic

    """
    from pydantic_ai.models.openai import OpenAIChatModel

    # Check for explicit override
    use_ollama_env = os.getenv("USE_OLLAMA", "").lower()
    force_ollama = use_ollama_env == "true"
    force_anthropic = use_ollama_env == "false"

    # ----------------------------------------------------------------------------
    # OLLAMA CONFIGURATION (Local LLM)
    # ----------------------------------------------------------------------------
    # Recommended models for this task (in order of capability):
    #   - devstral:24b-small-2505-q8_0  (best quality, requires ~16GB VRAM)
    #   - mistral:7b-instruct           (good balance, ~8GB VRAM)
    #   - llama3:8b                     (fast, ~8GB VRAM)
    #
    # To use a different model, change OLLAMA_MODEL below or set:
    #   export OLLAMA_MODEL="your-model-name"

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "devstral:24b-small-2505-q8_0")

    if not force_anthropic and (force_ollama or check_ollama_available(OLLAMA_BASE_URL)):
        print(f"      ✓ Using Ollama ({OLLAMA_MODEL})")
        print(f"        Endpoint: {OLLAMA_BASE_URL}")
        return OpenAIChatModel(
            model_name=OLLAMA_MODEL,
            provider=OllamaProvider(base_url=f"{OLLAMA_BASE_URL}/v1"),
        )

    # ----------------------------------------------------------------------------
    # ANTHROPIC CONFIGURATION (Cloud LLM)
    # ----------------------------------------------------------------------------
    # Uses Claude 3.5 Haiku for cost-effective classification.
    # Requires ANTHROPIC_API_KEY environment variable.
    #
    # To use a different model:
    #   export ANTHROPIC_MODEL="claude-sonnet-4-20250514"

    try:
        from pydantic_ai.models.anthropic import AnthropicModel

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Either:\n"
                "  1. Start Ollama: `ollama serve`\n"
                "  2. Set API key: `export ANTHROPIC_API_KEY='your-key'`"
            )

        ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        print(f"      ✓ Using Anthropic ({ANTHROPIC_MODEL})")
        return AnthropicModel(ANTHROPIC_MODEL)

    except ImportError:
        raise RuntimeError(
            "Neither Ollama nor Anthropic available.\n"
            "Install anthropic: pip install anthropic\n"
            "Or start Ollama: ollama serve"
        )


# ============================================================================
# CLASSIFICATION AGENT SETUP
# ============================================================================
# The Pydantic AI agent uses few-shot examples to guide classification.
# The @agent.instructions decorator dynamically injects record data into the prompt.


print("\n[5/6] Configuring classification agent...")

example_classifications = [
    RecordClassificationOutput(
        id="doi:123.45.67/89",
        title="Decision boundaries for group classifications in social circles",
        classification="graph based clustering",
        rationale=dedent(
            """
        Directly specifies applications of graph-based clustering and classification techniques as applied to social
        contexts.
        """
        ),
    ),
    RecordClassificationOutput(
        id="doi:167.45.67/12",
        title="Weather veins in Hawaii",
        classification="unrelated",
        rationale="This article completely unrelated to statistical topics.",
    ),
    RecordClassificationOutput(
        id="doi:125.68.93/48",
        title="Classifying uncertainty in scans for brain tumors using bayesian principles",
        classification="bayesian statistics",
        rationale=dedent(
            """
        This paper directly discusses the applications of bayesian analysis and uncertainty in classification in the
        in the classification of brain tumors as benign or cancerous.
        """
        ),
    ),
]


AGENT_INSTRUCTIONS = dedent(
    f"""
    ## Role
    You are an expert researcher conducting a large-scale systematic literature review.
    Your task is to classify academic papers into research categories based on their
    metadata and abstracts.

    ## Classification Categories
    1. **bayesian statistics**: Papers focusing on Bayesian inference, probabilistic
       modeling, prior/posterior distributions, MCMC methods, or Bayesian decision theory.

    2. **graph based clustering**: Papers on network analysis, community detection,
       graph partitioning, spectral clustering, or graph neural networks for grouping.

    3. **statistical innovation**: Papers introducing novel statistical methods,
       estimators, tests, or significant methodological advances.

    4. **unrelated**: Papers that don't fit the above categories or are primarily
       from other domains without statistical methodology focus.

    ## Classification Guidelines
    - Focus on the PRIMARY contribution of the paper
    - Consider both the title and abstract content
    - If a paper spans multiple categories, choose the most dominant theme
    - Provide clear, specific rationale for your classification

    ## Example Classifications

    {example_classifications[0]}

    {example_classifications[1]}

    {example_classifications[2]}
    """
)

# Initialize the model and agent
selected_model = select_model()

researcher_agent = Agent(
    selected_model,
    deps_type=RecordDataDependencies,
    output_type=RecordClassificationOutput,
    instructions=AGENT_INSTRUCTIONS,
)


@researcher_agent.instructions
def inject_record_context(ctx: RunContext[RecordDataDependencies]) -> str:
    """Dynamically inject the current record's metadata into the agent's context.

    This decorator function is called for each classification request, providing the agent with record-specific
    information formatted for optimal comprehension.

    """
    return dedent(
        f"""
        ## Current Record to Classify

        **Source Provider**: {ctx.deps.provider_name}
        **Title**: {ctx.deps.title}
        **Year**: {ctx.deps.year or "Not specified"}

        **Subjects**: {ctx.deps.subjects or "Not specified"}
        **Keywords**: {ctx.deps.keywords or "Not specified"}

        ---

        **Abstract**:
        {ctx.deps.abstract or "[No abstract available]"}

        ---

        **URL**: {ctx.deps.url or "Not available"}
        """
    )


# The prompt sent to the agent for each classification
CLASSIFICATION_PROMPT = dedent(
    """
    Classify the current record into one of the four categories:
    - bayesian statistics
    - graph based clustering
    - statistical innovation
    - unrelated

    Provide your classification and a brief rationale explaining your reasoning.
    """
)


# ============================================================================
# CLASSIFICATION INFERENCE FUNCTION
# ============================================================================


def retry_inference(fn):
    """Helper function used to repeat inference when it fails to produce expected results due to processing issues."""

    @wraps(fn)
    def wrapper(*args, max_attempts: int = 1, **kwargs):
        """Inner function wrapper used to repeat inference when it fails..."""
        if max_attempts < 1:
            max_attempts = 1

        for attempt in range(1, max_attempts + 1):
            # On success, return the result
            result = fn(*args, **kwargs)
            if result:
                return result
            else:
                # On failure, retry
                if attempt >= max_attempts:
                    print("Retries Exceeded")
                    return result
            print(f"Attempt {attempt}/{max_attempts} Failed. Retrying...")

    return wrapper


@retry_inference
def infer_classification(
    record: dict[str, Any] | RecordDataDependencies, message_history: Optional[list] = None, **kwargs
) -> RecordClassificationOutput | RecordClassificationError:
    """Classify a single academic record using the configured LLM agent.

    Accepts either a raw dictionary (from normalized records) or a pre-validated RecordDataDependencies instance.
    Returns a classification result or error object.

    """
    # Convert dict to validated model if needed
    if not isinstance(record, RecordDataDependencies):
        record = RecordDataDependencies.model_validate(
            {k: v for k, v in record.items() if k in RecordDataDependencies.model_fields}
        )

    try:
        result = researcher_agent.run_sync(
            CLASSIFICATION_PROMPT, deps=record, message_history=message_history, **kwargs
        )
        return result.output

    except Exception as e:
        return RecordClassificationError(
            id=str(record.record_id or "unknown"),
            title=str(record.title or "Unknown Title"),
            error=type(e).__name__,
            message=str(e),
        )


# ============================================================================
# EXECUTE CLASSIFICATION
# ============================================================================

print("\n[6/6] Classifying sample records...")

# For demonstration, classify the first 5 records
# In production, you might process all records or implement batching
SAMPLE_SIZE = 5
SHUFFLE = True
MAX_ATTEMPTS = 3

if SHUFFLE:
    shuffle(normalized_records)

sample_records = normalized_records[:SAMPLE_SIZE]

print(f"      Processing {SAMPLE_SIZE} records (of {len(normalized_records):,} total)...")
print("      " + "-" * 50)

classification_results = []
for i, record in enumerate(sample_records, start=1):
    title = record.get("title", "Unknown")[:60]
    print(f"      [{i}/{SAMPLE_SIZE}] Classifying: {title}...")
    result = infer_classification(record, max_attempts=MAX_ATTEMPTS)
    if result:
        print(f"              → {result.classification}")
    else:
        print(f"              → ERROR: {result.error}")
    classification_results.append(result)

# ============================================================================
# DISPLAY RESULTS
# ============================================================================

print("\n" + "=" * 70)
print("CLASSIFICATION RESULTS")
print("=" * 70)

successful = [r for r in classification_results if r]
failed = [r for r in classification_results if not r]

print(f"\nProcessed: {len(classification_results)} | Successful: {len(successful)} | Failed: {len(failed)}")

for i, result in enumerate(classification_results, 1):
    print(f"\n{'─' * 70}")
    print(f"Record {i}: {result.title[:70]}{'...' if len(result.title) > 70 else ''}")
    print(f"{'─' * 70}")

    if result:
        print(f"  Classification: {result.classification}")
        print(f"  Rationale: {result.rationale}")
    else:
        print(f"  ERROR: {result.error}")
        print(f"  Message: {result.message}")

print("\n" + "=" * 70)
print("PROCESSING COMPLETE")
print("=" * 70)
print(f"\nTotal records available for classification: {len(normalized_records):,}")
print("To classify all records, modify SAMPLE_SIZE or implement batch processing.")
print("\nTip: Results can be exported to CSV/JSON for further analysis.")
