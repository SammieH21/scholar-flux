"""Daily Literature Data Pipeline: Automated Article Retrieval and Accumulation.

This example demonstrates how to build an automated data preparation pipeline
using ScholarFlux that retrieves recently published articles, processes them
into a flat DataFrame-compatible format, and accumulates results over time
with automatic deduplication.

Use Case: Incremental Dataset Building
--------------------------------------
Researchers often need to maintain up-to-date datasets of literature on specific
topics. Manual approaches are tedious and error-prone:

- Remembering to check for new publications regularly
- Avoiding duplicate entries when merging new results
- Transforming nested API responses into analysis-ready formats
- Tracking what was retrieved and when

This pipeline solves these problems by:

1. Searching for articles published within a configurable time window
2. Encoding nested JSON responses for DataFrame/Parquet compatibility
3. Deduplicating against previously retrieved records
4. Persisting results with full audit logging

Workflow Overview
-----------------
1. **Configure**: Set global defaults via ``config_settings`` (user agent, cache backends)
2. **Search**: Query provider APIs with date filters to retrieve recent publications
3. **Process**: Use the internal processing pipeline to parse responses and process records
4. **Normalize**: Combine ScholarFlux's normalized schema with provider-specific fields
5. **Encode**: Use ``JsonDataEncoder`` to convert nested structures to JSON encoded records
6. **Deduplicate**: Merge with the existing dataset, removing duplicates by article ID
7. **Persist**: Save to Parquet format for efficient storage and retrieval

Key Concepts Demonstrated
-------------------------
- ``config_settings``: Global configuration without explicit parameter passing
- ``JsonDataEncoder``: Convert nested JSON structures into dumpable strings for tabular data formats and reload
- ``SearchResultList``: Batch operations (filter, join, normalize) on search results
- ``api_specific_parameters``: Provider-native query options (date filters, sorting)
- Incremental accumulation with deduplication

Requirements
------------
Core:
    - scholar_flux
    - pandas
    - pyarrow or fastparquet (for Parquet I/O)

Optional:
    - schedule (for automated daily runs)
    - redis (if using Redis cache backends)

Install with::

    pip install scholar_flux pandas pyarrow
    pip install schedule  # optional, for scheduling

Running the Pipeline
--------------------
One-shot execution (run once and exit)::

    python retrieval_pipeline_orchestration.py

Scheduled execution (run daily at specified time)::

    python retrieval_pipeline_orchestration.py --schedule
    python retrieval_pipeline_orchestration.py --schedule --time 09:30

The ``--run-immediately`` flag (default: True) executes the pipeline once on
startup before entering the schedule loop, useful for verifying configuration.

Expected Output
---------------
First run::

    2025-12-10 15:38:44 - INFO - Writing 48 records to output/plos_records.parquet...

Subsequent runs (no new articles)::

    2025-12-10 15:42:50 - INFO - No new records retrieved after deduplication

Log files are written to the output directory with rotation support for
long-running scheduled pipelines.

Configuration
-------------
The pipeline uses ``config_settings`` to establish defaults that apply globally:

.. code-block:: python

    config_settings.set("SCHOLAR_FLUX_DEFAULT_MAILTO", "your@email.com")
    config_settings.set("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE", "redis")

These settings apply to all ScholarFlux operations without needing to pass
them explicitly to each function call. See :doc:`getting_started` for the
full list of configuration options.

Customization
-------------
To adapt this pipeline for your use case:

1. **Change the provider**: Modify ``PROVIDER_NAME`` (plos, crossref, pubmed, etc.)
2. **Adjust the query**: Set ``QUERY`` to your research topic
3. **Modify date range**: Change ``DATE_LOOKBACK_DAYS`` for your update frequency
4. **API-specific filters**: Update ``API_SPECIFIC_PARAMETERS`` for your provider

Note that ``api_specific_parameters`` are provider-specific. The date filter
syntax shown here (``fq=publication_date:[DATE TO *]``) works for PLOS but
other providers use different parameter names and formats.

See Also
--------
- :doc:`getting_started` - Basic ScholarFlux usage and configuration
- :doc:`schema_normalization` - Understanding normalized vs raw record fields
- :doc:`caching_strategies` - Production caching with Redis/MongoDB
- :doc:`advanced_workflows` - Multi-step retrieval patterns

"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent
import re

import pandas as pd

from scholar_flux import SearchCoordinator, logger as scholar_flux_logger
from scholar_flux.api.models import SearchResultList
from scholar_flux.exceptions import NoRecordsAvailableException
from scholar_flux.utils import config_settings, setup_logging, JsonDataEncoder

# ============================================================================
# SCHOLARFLUX CONFIGURATION
# ============================================================================
# Global settings that apply to all ScholarFlux operations in this module.
# These defaults are used when explicit parameters aren't provided to
# SearchCoordinator or SearchAPI constructors.
#
# Benefits of config_settings:
# - Centralized configuration in one place
# - No need to pass common parameters to every function
# - Easy to override for specific use cases
# ============================================================================

# Identify your application to API providers (required by some, polite for all)
config_settings.set("SCHOLAR_FLUX_DEFAULT_USER_AGENT", "LiteratureDataPipeline/1.0 (scholar.flux)")

# Email for API providers that offer higher rate limits for identified users (Crossref "polite pool", OpenAlex, CORE)
# config_settings.set("SCHOLAR_FLUX_DEFAULT_MAILTO", "researcher@university.edu")

# Layer 1: HTTP response caching (raw API responses)
# Options: sqlite (default), redis, mongodb, memory
config_settings.set("SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND", "redis")

# Layer 2: Processed result caching (after extraction/transformation)
# Options: sqlite, null (No-Op), redis, mongodb, memory (default)
config_settings.set("SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE", "redis")


# ============================================================================
# LOGGING SETUP
# ============================================================================
# Two loggers are used:
# 1. scholar_flux logger: Internal library logging (API calls, cache hits, etc.)
# 2. pipeline_logger: Pipeline-specific operational logging (records retrieved, etc.)
#
# This separation allows independent control over verbosity levels.
# ============================================================================

scholar_flux_logger.setLevel(logging.DEBUG)
scholar_flux_logger.propagate = False

pipeline_logger = logging.getLogger("data_pipeline")
pipeline_logger.propagate = False


# ============================================================================
# PIPELINE FUNCTIONS
# ============================================================================


def clean_filename(filename: str) -> str:
    """Simple method used to parse and remove non-alphanumeric characters from filenames.

    Useful for when using queries as part of a filename when special characters otherwise
    cause issues.

    Args:
        filename:
            The name of the file to clean special characters from

    Returns:
        A filename that is cleaned of all special characters (i.e parentheses, brackets, etc.)

    """
    cleaned_filename = re.sub(r"[^a-zA-Z0-9._]", "", filename.replace(" ", "_")).lower()
    return cleaned_filename


def from_date(days: int = 1) -> datetime:
    """Calculate a date N days in the past from today.

    Useful for constructing date range filters to retrieve only recent
    publications.

    Args:
        days: Number of days to look back. Negative values are converted
            to positive (i.e., ``from_date(-7)`` and ``from_date(7)`` are
            equivalent).

    Returns:
        A datetime object representing midnight N days ago.

    Examples:
        >>> from_date(1)   # Yesterday
        datetime.datetime(2025, 12, 9, 0, 0, 0)

        >>> from_date(30)  # 30 days ago
        datetime.datetime(2025, 11, 10, 0, 0, 0)

    """
    days = abs(days)
    return datetime.now() - timedelta(days=days)


def create_coordinator(
    provider_name: str = "plos",
    query: str = "machine learning",
    records_per_page: int = 25,
    **kwargs,
) -> SearchCoordinator:
    """Create a SearchCoordinator configured for the data pipeline.

    The coordinator is configured with a ``PassthroughDataProcessor`` (the default)
    that retains the structure of nested JSON structures as is. Given that nested objects
    (common in API data structures) are not suitable for storage, the pipeline later uses
    a ``JsonDataEncoder`` class to recursively encode and convert nested objects into JSON
    to generate a data set suitable for parquet storage.

    The exact structure can later be reloaded into a format suitable for DataFrames.

    Args:
        provider_name: API provider to search. Supported providers include
            'plos', 'crossref', 'pubmed', 'arxiv', 'openalex', 'core',
            'springernature'.
        query: Search query string.
        records_per_page: Number of records to retrieve per page. Maximum
            values vary by provider (PLOS: 100, Crossref: 1000, etc.).
        **kwargs: Additional arguments passed to SearchCoordinator, such as
            ``api_specific_parameters`` for provider-native query options.

    Returns:
        A configured SearchCoordinator instance ready for searching.


    """
    coordinator = SearchCoordinator(
        query=query,
        provider_name=provider_name,
        records_per_page=records_per_page,
        **kwargs,
    )

    pipeline_logger.debug(
        f"Created coordinator: provider={provider_name}, query='{query}', " f"records_per_page={records_per_page}"
    )

    return coordinator


def search_papers(
    coordinator: SearchCoordinator,
    page_range: int | list[int] | range = 5,
    **kwargs,
) -> SearchResultList:
    """Execute a paginated search using the provided coordinator.

    Args:
        coordinator: A configured SearchCoordinator instance.
        page_range: Pages to retrieve. Can be:
            - An integer N: retrieves pages 1 through N
            - A list of specific page numbers: [1, 3, 5]
            - A range object: range(1, 6)
        **kwargs: Additional arguments passed to ``search_pages()``.

    Returns:
        A SearchResultList containing results from all requested pages.
        Use ``.filter()`` to remove failed responses and ``.join()`` to
        combine all records into a single list.

    Examples:
        >>> results = search_papers(coordinator, page_range=3)  # Pages 1-3
        >>> results = search_papers(coordinator, page_range=[1, 5, 10])
        >>> results = search_papers(coordinator, page_range=range(1, 11, 2))  # Odd pages 1-9

    """
    if isinstance(page_range, int):
        page_range = range(1, page_range + 1)

    pipeline_logger.info(f"Searching pages {list(page_range)}...")
    search_results = coordinator.search_pages(page_range, **kwargs)
    pipeline_logger.info(f"Search complete: {search_results.record_count} records from " f"{len(search_results)} pages")

    return search_results


def postprocess_papers(search_results: SearchResultList) -> pd.DataFrame:
    """Transform search results into a pandas DataFrame.

    Combines ScholarFlux's normalized schema (consistent field names across
    providers) with the original provider-specific fields, giving you both
    standardized access and full raw data.

    Args:
        search_results: A SearchResultList from ``search_papers()``.

    Returns:
        A DataFrame where each row is an article record. Columns include
        both normalized fields (title, abstract, doi, authors, etc.) and
        provider-specific fields.

    Raises:
        NoRecordsAvailableException: If no records were retrieved, either
            due to API errors or a query that matched no results.

    Note:
        When both normalized and raw fields have the same name, the
        normalized value takes precedence (dict union behavior: ``a | b``
        keeps values from ``b`` for duplicate keys).

        Also note that the encoder.dumps and encoder.loads implementation is idempotent
        with lists, dicts, and other common data types. That is, calling
        `series.apply(JsonDataEncoder.dumps).apply(JsonDataEncoder.loads)` to serialize each
        element in the series should return the same structure as the original series.

    """
    if not search_results.record_count:
        err = dedent(
            """
            No records returned from search.

            Possible causes:
            - The API may be temporarily unavailable
            - Query returned no matches for the specified filters
            - Date range filter excluded all results

            Check the query parameters and try again.
            """
        )
        raise NoRecordsAvailableException(err)

    # normalized records: consistent schema across all providers
    # non-normalized records: original provider-specific fields
    normalized_records = search_results.normalize()

    non_normalized_records = search_results.join(strip_annotations=True)  # removes _extraction_index, _record_id

    # Merge both, with normalized fields taking precedence, removing internal record metadata fields
    combined_records = [
        non_normalized | normalized for normalized, non_normalized in zip(normalized_records, non_normalized_records)
    ]

    combined_df = pd.DataFrame(combined_records)

    # Stringify and encode lists and dictionaries when required:
    for key in combined_df.columns:
        if any(isinstance(x, (list, dict)) for x in combined_df[key].values):
            combined_df[key] = combined_df[key].apply(JsonDataEncoder.dumps)

    pipeline_logger.debug(f"Created DataFrame with {len(combined_df)} rows, {len(combined_df.columns)} columns")

    return combined_df


def accumulate_results(
    article_df: pd.DataFrame,
    storage_filename: str = "articles.parquet",
    storage_directory: str | Path | None = None,
    id_column: str = "id",
) -> pd.DataFrame | None:
    """Append new records to an existing dataset with deduplication.

    If the storage file exists, new records are merged with existing data
    and duplicates (by article ID) are removed. If the file doesn't exist,
    it's created with the new records.

    Args:
        article_df: DataFrame of new article records to accumulate.
        storage_filename: Name of the Parquet file for storage.
        storage_directory: Directory for storage file. If None, uses
            current working directory.
        id_column: Column name used for deduplication. Defaults to 'id',
            which is the normalized article identifier in ScholarFlux.

    Returns:
        The combined DataFrame after deduplication, or None if no new
        records were added (all records were duplicates).

    Raises:
        ImportError: If pyarrow or fastparquet is not installed.

    Note:
        This function uses Parquet format for efficient columnar storage.
        Parquet requires flat data structures, which is why the pipeline
        uses ``JsonDataEncoder.dumps()`` to encode nested fields as strings.
        The exact structure can easily be reloaded by via using
        ``combined_df.apply(JsonDataEncoder.loads)``, which will target
        only encoded values that contain the string prefix HASHBYTES.

    """
    storage_path = Path(storage_directory) / storage_filename if storage_directory else Path(storage_filename)

    if storage_path.exists():
        pipeline_logger.debug(f"Loading existing records from {storage_path}")
        existing_df = pd.read_parquet(storage_path)

        # Identify which new records are truly new (not in existing dataset)
        is_new = ~article_df[id_column].isin(existing_df[id_column])
        new_record_count = is_new.sum()

        if new_record_count == 0:
            pipeline_logger.info(f"No new records to add (all {len(article_df)} records already exist)")
            return None

        # Combine and deduplicate
        combined_df = pd.concat([existing_df, article_df]).drop_duplicates(subset=[id_column])

        pipeline_logger.info(f"Adding {new_record_count} new records to {storage_path} " f"(total: {len(combined_df)})")

    else:
        combined_df = article_df
        pipeline_logger.info(f"Creating new dataset with {len(combined_df)} records at {storage_path}")

    # Ensure parent directory exists
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    combined_df.to_parquet(storage_path, index=False)
    pipeline_logger.debug(f"Saved {len(combined_df)} records to {storage_path}")

    return combined_df


def run_pipeline(
    page_range: int | list[int] | range,
    output_filename: str | None = None,
    output_directory: Path | str | None = None,
    **kwargs,
) -> pd.DataFrame | None:
    """Execute the complete data retrieval pipeline.

    Orchestrates the full workflow: create coordinator → search → process →
    accumulate. Handles errors gracefully with appropriate logging.

    Args:
        page_range: Pages to retrieve (see ``search_papers`` for formats).
        output_filename: Parquet filename for accumulated results. If None,
            results are returned but not persisted.
        output_directory: Directory for output file.
        **kwargs: Arguments passed to ``create_coordinator()``, including:
            - provider_name: API provider to search
            - query: Search query string
            - records_per_page: Records per page
            - api_specific_parameters: Provider-native query options

    Returns:
        DataFrame of retrieved records, or None if no records were found
        or an error occurred.

    Examples:
        >>> # One-shot retrieval without persistence
        >>> df = run_pipeline(page_range=3, query="CRISPR", provider_name="plos")

        >>> # Retrieval with accumulation
        >>> df = run_pipeline(
        ...     page_range=5,
        ...     output_filename="crispr_papers.parquet",
        ...     output_directory="./data",
        ...     query="CRISPR",
        ...     provider_name="plos",
        ... )

    """
    coordinator = create_coordinator(**kwargs)

    try:
        search_results = search_papers(coordinator, page_range=page_range)
        article_df = postprocess_papers(search_results)

        if output_filename:
            accumulate_results(
                article_df,
                storage_filename=output_filename,
                storage_directory=output_directory,
            )

        return article_df

    except NoRecordsAvailableException:
        pipeline_logger.warning(f"No records retrieved for query '{coordinator.api.query}'")
        return None

    except Exception as e:
        pipeline_logger.error(
            f"Pipeline failed with {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None


# ============================================================================
# CLI ENTRY POINT
# ============================================================================


def main():
    """Command-line interface for the data pipeline."""
    parser = argparse.ArgumentParser(
        description="Daily literature data pipeline for automated article retrieval",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """
            Examples:
              # Run once (default)
              python retrieval_pipeline_orchestration.py

              # Run on a daily schedule at 8:00 AM
              python retrieval_pipeline_orchestration.py --schedule

              # Run daily at a custom time
              python retrieval_pipeline_orchestration.py --schedule --time 09:30

              # Skip immediate execution when scheduling
              python retrieval_pipeline_orchestration.py --schedule --no-run-immediately
            """
        ),
    )

    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run on a daily schedule instead of once",
    )
    parser.add_argument(
        "--time",
        default="08:00",
        help="Time to run daily in HH:MM format (default: 08:00)",
    )
    parser.add_argument(
        "--run-immediately",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run pipeline immediately on startup before entering schedule loop (default: True)",
    )

    args = parser.parse_args()

    # ========================================================================
    # PIPELINE CONFIGURATION
    # ========================================================================
    # Customize these parameters for your use case.
    # ========================================================================

    PROVIDER_NAME = "plos"
    QUERY = "Public Health AND Water Sanitization"
    RECORDS_PER_PAGE = 100  # PLOS max: 100, Crossref max: 1000
    PAGE_RANGE = range(1, 5)  # Pages 1-10. Stops early if no more pages are available.

    # Date filter: retrieve articles from the last N days
    DATE_LOOKBACK_DAYS = 30
    DATE_FROM = from_date(days=DATE_LOOKBACK_DAYS).strftime("%Y-%m-%d") + "T00:00:00Z"
    DATE_TO = "*"  # Now

    # Output configuration
    OUTPUT_DIRECTORY = Path("./output")
    OUTPUT_FILENAME = clean_filename(f"{PROVIDER_NAME}_{QUERY}_records.parquet")
    LOG_FILENAME = "data_pipeline.log"

    # Provider-specific parameters (PLOS syntax shown here)
    # Other providers use different parameter names and formats
    API_SPECIFIC_PARAMETERS = {
        "sort": "publication_date desc",
        "fq": f"publication_date:[{DATE_FROM} TO {DATE_TO}]",
    }

    # ========================================================================
    # LOGGING INITIALIZATION
    # ========================================================================

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    setup_logging(
        pipeline_logger,
        log_directory=str(OUTPUT_DIRECTORY),
        log_level=logging.INFO,
        log_file=LOG_FILENAME,
        backup_count=7,  # Keep 7 days of logs for scheduled runs
    )

    # ========================================================================
    # PIPELINE EXECUTION
    # ========================================================================

    pipeline_params = {
        "page_range": PAGE_RANGE,
        "output_filename": OUTPUT_FILENAME,
        "output_directory": OUTPUT_DIRECTORY,
        "query": QUERY,
        "provider_name": PROVIDER_NAME,
        "records_per_page": RECORDS_PER_PAGE,
        "api_specific_parameters": API_SPECIFIC_PARAMETERS,
        "cache_requests": True,
    }

    search_summary = dedent(
        f"""
        ========================================================================
        Literature Data Pipeline
        ========================================================================
        Provider:           {PROVIDER_NAME}
        Query:              '{QUERY}'
        Records per page:   {RECORDS_PER_PAGE}
        Pages to fetch:     {len(PAGE_RANGE)} (up to {len(PAGE_RANGE) * RECORDS_PER_PAGE} records)
        Date filter:        Last {DATE_LOOKBACK_DAYS} days
        Output:             {OUTPUT_DIRECTORY / OUTPUT_FILENAME}
        ========================================================================
        """
    )

    if args.schedule:
        try:
            import schedule
        except ImportError:
            pipeline_logger.error(
                "The 'schedule' package is required for scheduled execution. " "Install it with: pip install schedule"
            )
            return

        pipeline_logger.info(f"Scheduling pipeline to run daily at {args.time}")
        pipeline_logger.info(search_summary)

        schedule.every().day.at(args.time).do(
            lambda: (
                pipeline_logger.info(f"Scheduled run starting at {datetime.now()}"),
                run_pipeline(**pipeline_params),
            )
        )

        if args.run_immediately:
            pipeline_logger.info("Running pipeline immediately before entering schedule loop...")
            run_pipeline(**pipeline_params)

        pipeline_logger.info(
            f"Entering schedule loop. Pipeline will run daily at {args.time}. " "Press Ctrl+C to exit."
        )

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            pipeline_logger.info("Pipeline scheduler stopped by user")

    else:
        # One-shot execution
        pipeline_logger.info(search_summary)
        run_pipeline(**pipeline_params)
        pipeline_logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
