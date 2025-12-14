"""Semantic Similarity Search: Finding Interdisciplinary Research with Embeddings.

This example demonstrates how to combine ScholarFlux's academic search capabilities
with transformer-based embeddings to discover papers at the intersection of multiple
research domains. Specifically, we search for econometric papers and rank them by
their semantic similarity to public health topics.

Use Case: Interdisciplinary Literature Discovery
------------------------------------------------
Researchers often need to find papers that bridge multiple fields. Traditional
keyword search struggles with this because:
- Different fields use different terminology for similar concepts
- Interdisciplinary papers may not explicitly mention all relevant fields
- Semantic relationships aren't captured by exact string matching

This example solves this by:
1. Searching Springer Nature for "Econometric" papers focused on "Suburban" areas
2. Computing semantic embeddings for each paper's title + abstract
3. Ranking papers by cosine similarity to the concept "Public Health"

Workflow Overview
-----------------
1. **API Search**: Use ScholarFlux to retrieve papers from Springer Nature
2. **Normalization**: Transform API responses into a consistent record format
3. **Embedding Generation**: Encode paper text using ModernBERT
4. **Similarity Ranking**: Compute cosine similarity to target topic
5. **Visualization**: Plot similarity distribution and show top matches

Key Concepts Demonstrated
-------------------------
- `SearchAPI`: Low-level API client with provider-specific parameters
- `SearchCoordinator`: Orchestrates search, processing, and caching
- `DataCacheManager`: SQLite-based response caching
- `CachedSessionManager`: HTTP request caching to reduce API calls (1-day TTL)
- Provider-specific parameters: `sort` and `keyword` for Springer Nature

Requirements
------------
Core:
- scholar_flux
- pandas
- numpy

ML/Visualization:
- transformers (HuggingFace)
- torch
- scikit-learn
- matplotlib
- seaborn

Install with:
    pip install scholar_flux pandas numpy transformers torch scikit-learn matplotlib seaborn

Model Information
-----------------
This example uses ModernBERT (answerdotai/ModernBERT-base), a 2024 architecture
that improves on BERT with:
- Rotary positional embeddings (RoPE)
- 8192 token context length
- Faster inference than original BERT

For resource-constrained environments, alternatives include:
- sentence-transformers/all-MiniLM-L6-v2 (smaller, faster)
- BAAI/bge-small-en-v1.5 (optimized for similarity)

Expected Output
---------------
- Similarity distribution histogram saved to 'embedding_similarity_dist.png'
- Top 5 papers ranked by similarity to "Public Health" printed to console
- Processing typically yields 80-100 papers from 5 pages of results

"""

from __future__ import annotations

from scholar_flux import SearchCoordinator, SearchAPI, DataCacheManager, CachedSessionManager
from scholar_flux.exceptions import NoRecordsAvailableException, MissingAPIKeyException
from pprint import pprint
import logging
from typing import TYPE_CHECKING
from textwrap import dedent

# Type hints for optional dependencies (doesn't require import at runtime)
if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from transformers import AutoModel, AutoTokenizer


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
# ScholarFlux logs API requests, cache hits/misses, and processing steps.
# Useful for debugging slow queries or unexpected results.

logger = logging.getLogger("scholar_flux")
logger.setLevel(logging.INFO)
logger.propagate = False


# ============================================================================
# SEARCH CONFIGURATION
# ============================================================================

print("\n" + "=" * 70)
print("SCHOLARFLUX SEMANTIC SIMILARITY SEARCH")
print("=" * 70)
print("\n[1/6] Configuring search parameters...")

# ----------------------------------------------------------------------------
# Search Parameters
# ----------------------------------------------------------------------------
# These parameters define the scope of our academic search:
#
# - QUERY: Primary search term for the main topic (Econometric)
# - KEYWORD: Secondary filter within results (Suburban)
# - TOPIC_FOR_SIMILARITY: Concept we'll measure semantic distance to (Public Health)
#
# The goal is to find Econometric papers about Suburban areas that are
# semantically similar to Public Health research.

QUERY = "Econometric"
KEYWORD = "Suburban"
TOPIC_FOR_SIMILARITY = "Public Health"
RECORDS_PER_PAGE = 20
SORT_BY_DATE = "createdDate"
PAGE_RANGE = range(1, 6)  # Pages 1-5 (up to 100 records)

print(f"      Query: '{QUERY}'")
print(f"      Keyword filter: '{KEYWORD}'")
print(f"      Similarity target: '{TOPIC_FOR_SIMILARITY}'")
print(f"      Pages to fetch: {len(PAGE_RANGE)} (up to {len(PAGE_RANGE) * RECORDS_PER_PAGE} records)")

# ============================================================================
# SCHOLARFLUX API SETUP
# ============================================================================

print("\n[2/6] Initializing ScholarFlux components...")

# Temporary request cache (TTL = 1 day)
session = CachedSessionManager(backend="sqlite", user_agent="ResearchProject/1.0:scholar.flux").configure_session()

# The API client for retrieving search information.
search_api = SearchAPI(
    query=QUERY, provider_name="SpringerNature", records_per_page=RECORDS_PER_PAGE, session=session  # case insensitive
)

# Orchestrates the full retrieval, processing, and caching pipeline. NOTE: The processing cache requires SQLAlchemy
springer_search_coordinator = SearchCoordinator(
    search_api=search_api,
    cache_manager=DataCacheManager.with_storage("sql"),  # response processing cache
)


if not search_api.api_key:
    raise MissingAPIKeyException(
        dedent(
            """
        The SpringerNature API provider requires an API key!

        Visit the following link and sign up on the developer portal to request an API key:

        https://dev.springernature.com/docs/quick-start/api-access/
        """
        )
    )

# Retrieves results for a page range - reference key value paired arguments from the original API to further customize
search_results = springer_search_coordinator.search_pages(
    PAGE_RANGE,
    sort=SORT_BY_DATE,  # springer nature-specific parameter for sorting from newest to oldest
    keyword=KEYWORD,  # springer nature-specific parameter for finding economic abstracts that focus on suburban areas
)

# If the search_results list is empty
if not search_results.record_count:
    err = dedent(
        """
        ✗ ERROR: No records returned..
        Possible causes:
        - The Springer Nature API may be unavailable
        - Query returned no matches
        - Invalid API key for Springer Nature
        Halting processing...
        """
    )
    raise NoRecordsAvailableException(err)

# Filter out failed pages and report success rate
successfully_processed_results = search_results.filter()
print(f"Successfully Retrieved {len(successfully_processed_results)} / {len(search_results)} pages")

# ----------------------------------------------------------------------------
# Normalize Records
# ----------------------------------------------------------------------------
# normalize() transforms provider-specific response formats into a unified
# schema with consistent field names: title, abstract, doi, authors, year, etc.

record_list = successfully_processed_results.normalize()
print(f"Total records: {len(record_list)}")


# ============================================================================
# ML DEPENDENCIES CHECK
# ============================================================================
# The following section requires ML libraries. We check for their availability
# and provide helpful installation instructions if missing.

print("\n[4/6] Loading ML dependencies...")

try:
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from transformers import AutoModel, AutoTokenizer

    print("      ✓ pandas, numpy, matplotlib, seaborn")
    print("      ✓ transformers (HuggingFace)")

except ImportError as e:
    missing_package = str(e).split("'")[1] if "'" in str(e) else str(e)
    print(f"\n      ✗ ERROR: Missing required package: {missing_package}")
    print("\n      Install ML dependencies with:")
    print("      pip install pandas numpy matplotlib seaborn transformers torch")

sns.set_style("darkgrid")

# ============================================================================
# EMBEDDING MODEL SETUP
# ============================================================================

print("\n[5/6] Loading embedding model...")

# ----------------------------------------------------------------------------
# Model Selection
# ----------------------------------------------------------------------------
# ModernBERT is a 2024 update to the BERT architecture with improved performance.
# First run will download the model (~400MB). Subsequent runs use cached weights.
#
# Alternative models (smaller/faster):
#   MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
#   MODEL_ID = "BAAI/bge-small-en-v1.5"

MODEL_ID = "answerdotai/ModernBERT-base"

print(f"      Model: {MODEL_ID}")
print("      (First run downloads ~400MB, subsequent runs use cache)")

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModel.from_pretrained(MODEL_ID)

print("      ✓ Model loaded successfully")


def encode_text(text, model=model, tokenizer=tokenizer) -> np.ndarray:
    """Generate a dense vector embedding for input text.

    Uses mean pooling over the last hidden layer to create a fixed-size representation regardless of input length.

    """
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = model(**inputs)
    # Use the mean of the last layer's features as the paper's embedding
    embedding = outputs.last_hidden_state.mean(dim=1).detach().numpy()
    return embedding


def cosine_similarity(A: np.ndarray, B: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Returns a value between -1 (opposite) and 1 (identical). For normalized embeddings, this measures semantic
    similarity.

    """
    _A = A.flatten()
    _B = B.flatten()
    dot_product = np.dot(_A, _B)

    norm_a = np.linalg.norm(_A)
    norm_b = np.linalg.norm(_B)

    # Avoid division by zero
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


# ============================================================================
# COMPUTE EMBEDDINGS AND SIMILARITY
# ============================================================================

economy_df = pd.DataFrame(record_list)
print(f"Total records: {len(economy_df)}")
print(f"Columns: {', '.join(economy_df.columns[:8])}...")

# Null Checks for Common Columns
print(f"Null Columns:\n {economy_df.isnull().sum()}")


# ----------------------------------------------------------------------------
# Generate Topic Embedding
# ----------------------------------------------------------------------------
# This is our "target" - we'll measure how similar each paper is to this concept.

topic_description = "Public Health"
print(f"\nEncoding target topic: '{topic_description}'...")

topic_embedding = encode_text(topic_description)

# ----------------------------------------------------------------------------
# Prepare Article Text
# ----------------------------------------------------------------------------
# Combine title and abstract for richer semantic representation.
# Filter out records with insufficient text content.

economy_df["article"] = economy_df.title + ": " + economy_df.abstract
economy_df["text_length"] = economy_df["article"].str.len()

# Require at least 30 characters (filters out empty/minimal abstracts)
MIN_TEXT_LENGTH = 30

sufficient_length = economy_df["text_length"] > MIN_TEXT_LENGTH

filtered_economy_df = economy_df.loc[sufficient_length, :].copy()
total_filtered = len(economy_df) - len(filtered_economy_df)
print(f"Filtered {total_filtered} records with insufficient text.")
print(f"Processing {len(filtered_economy_df)} records with valid text...")

# ----------------------------------------------------------------------------
# Generate Paper Embeddings
# ----------------------------------------------------------------------------
# This is the computationally intensive step. For large datasets, consider:
# - Batch processing with model.encode() if using sentence-transformers
# - GPU acceleration (move model to CUDA)
# - Caching embeddings to disk

print("Generating embeddings (this may take a minute)...")
filtered_economy_df["embedding"] = filtered_economy_df.article.apply(encode_text)
print("✓ Embeddings computed")

filtered_economy_df["similarity"] = filtered_economy_df.embedding.apply(
    lambda article_embedding: cosine_similarity(article_embedding, B=topic_embedding)
)
print("✓ Similarity scores computed")

# ============================================================================
# RESULTS VISUALIZATION
# ============================================================================

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)

# ----------------------------------------------------------------------------
# Similarity Statistics
# ----------------------------------------------------------------------------

stats = filtered_economy_df["similarity"].describe()
print("\nSimilarity Distribution:")
print(f"  Mean:   {stats['mean']:.4f}")
print(f"  Std:    {stats['std']:.4f}")
print(f"  Min:    {stats['min']:.4f}")
print(f"  Max:    {stats['max']:.4f}")

OUTPUT_FILENAME = "embedding_similarity_dist.png"
fig, ax = plt.subplots()
# ax = filtered_economy_df.similarity.plot.hist(bins=20, ax = ax)
sns.histplot(filtered_economy_df["similarity"], kde=True, ax=ax, color="steelblue", bins=20)

ax.set_title(
    "Cosine Similarity of the topic, 'Public Health' with Abstracts Retrieved with \n"
    f"Query='{search_api.query}' and Keyword='{KEYWORD}'",
    fontsize=12,
)
ax.set_xlabel("Cosine Similarity")
plt.savefig(OUTPUT_FILENAME)
print(f"✓ Plot saved to: {OUTPUT_FILENAME}")

plt.show()

# Sorts the by cosine similarity in descending order
ranked_economy_df = filtered_economy_df.sort_values("similarity", ascending=False)

# Show the top 5 Economy articles that are most similar to the topic, "Public Health"
w = 115
SECTION_BREAK = "=" * w
TOP_N = 5
print(f"TOP {TOP_N} PAPERS MOST SIMILAR TO '{TOPIC_FOR_SIMILARITY.upper()}'")
for i, row in enumerate(ranked_economy_df.head(TOP_N).itertuples()):
    title_similarity = f"Rank {i + 1}: {row.title} (similarity={row.similarity:.3})"
    print(title_similarity)
    print(f"Publication Date: {row.date_published}")
    print(min(len(title_similarity), w) * "-" + "\n")
    pprint(f"Article: {row.abstract}", width=w)
    print(f"{'-'*w}\n")

summary = dedent(
    f"""
    {SECTION_BREAK}
    ANALYSIS COMPLETE
    {SECTION_BREAK}
    Total papers analyzed: {len(ranked_economy_df)}
    Similarity range: {stats['min']:.4f} to {stats['max']:.4f}
    Results saved to: {OUTPUT_FILENAME}
    Next steps:
      - Export df_valid to CSV for further analysis
      - Adjust TOPIC_FOR_SIMILARITY to explore different intersections
      - Try different embedding models for comparison
    """
)
print(summary)
