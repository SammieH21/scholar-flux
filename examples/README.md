# ScholarFlux Examples

Production-quality example templates demonstrating how ScholarFlux integrates with AI/ML and data orchestration pipelines.

## Available Examples

### [Retrieval Pipeline Orchestration](retrieval_pipeline_orchestration.py)
Automated daily literature retrieval with date filtering, deduplication, and Parquet export. Shows scheduled pipeline patterns for incremental dataset building.

### [Semantic Similarity Search](ml_springer_nature_embeddings_similarity.py)
Embedding-based interdisciplinary paper discovery using ModernBERT. Demonstrates ranking papers by semantic similarity to target topics.

### [Agentic Literature Review](agentic_literature_review.py)
Multi-provider concurrent search with LLM-powered classification via PydanticAI. Shows integration with AI agent frameworks.

## Documentation

For detailed tutorials and API reference: https://SammieH21.github.io/scholar-flux/

## Requirements

Each example includes its own requirements section. Generally you'll need:
- `scholar-flux` - Core package
- Provider-specific dependencies (see each file)
- Optional: `redis`, ML libraries (transformers, torch), or agentic frameworks (pydantic-ai)

## Running Examples

Each example is standalone and can be run directly:
```bash
python retrieval_pipeline_orchestration.py
python ml_springer_nature_embeddings_similarity.py
python agentic_literature_review.py
```

See individual file docstrings for detailed usage instructions.
