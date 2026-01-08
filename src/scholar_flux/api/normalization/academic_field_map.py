# scholar_flux.api.normalization.academic_field_map.py
"""The scholar_flux.api.normalization.academic_field_map implements the `AcademicFieldMap` for record normalization.

This implementation subclasses the `NormalizingFieldMap` class for use in academic record normalization by defining
additional combinations of fields that apply solely to academic APIs and databases.

Architecture Context:
    This layer is the third step in a 3 part configuration system tailored to each individual provider.

    1. Parameter Map (BaseAPIParameterMap) - Translates search parameters to provider-specific API parameters
    2. Metadata Map (ResponseMetadataMap) - Extracts pagination metadata (total hits, records per page)
    3. Field Map (AcademicFieldMap) - Normalizes provider-specific fields into a universal schema

    All three layers compose via ProviderConfig for complete provider integration:

    >>> from scholar_flux.api.providers import provider_registry
    >>> config = provider_registry.get("plos")
    >>> config.parameter_map  # Request building
    >>> config.metadata_map   # Pagination intelligence
    >>> config.field_map      # Response normalization

Design Philosophy:
    - **Minimal defaults**: Works out-of-box for common use cases
    - **Provider-specific when needed**: Subclasses override `_post_process()` for domain logic
    - **User-extensible**: Users can customize or replace field maps entirely

    This is NOT a rigid framework—each provider handles genuinely different data structures.
    The base class provides common helpers, not enforced patterns.

"""
from typing import Optional, Sequence
import datetime
import re
from scholar_flux.api.normalization.normalizing_field_map import NormalizingFieldMap
from scholar_flux.api.validators import validate_url, validate_bool_str
from scholar_flux.utils.record_types import NormalizedRecordType
from scholar_flux.utils.helpers import (
    unlist_1d,
    get_nested_data,
    try_none,
    try_compile,
    coerce_str,
    extract_year,
    parse_iso_timestamp,
    build_iso_date,
    coerce_flattened_str,
    strip_html_tags,
    as_tuple,
)

URL_PATTERN_SUFFIX = "(?=http)"
URL_PATTERN = try_compile(r"; *|, *|\| *", suffix=URL_PATTERN_SUFFIX)


class AcademicFieldMap(NormalizingFieldMap):
    """Extends the `NormalizingFieldMap` to customize field extraction and processing for academic record normalization.

    This class is used to normalize the names of academic data fields consistently across provider. By default, the
    AcademicFieldMap includes fields for several attributes of academic records including:

    1. Core identifiers (e.g. `doi`, `url`, `record_id`)
    2. Bibliographic metadata ( `title`, `abstract`, `authors`)
    3. Publication metadata (`journal`, `publisher`, `year`, `date_published`, `date_created`)
    4. Content and classification (`keywords`, `subjects`, `full_text`)
    5. Metrics and impact (`citation_count`)
    6. Access and rights (`open_access`, `license`)
    7. Document metadata (`record_type`, `language`)
    8. All other fields that are relevant to only the current API (`api_specific_fields`)

    During normalization, the `AcademicFieldMap.fields` property returns all subclassed field mappings as a flattened
    dictionary (excluding private fields prefixed with underscores). Both simple and nested API-specific
    field names are matched and mapped to universal field names.

    Any changes to the instance configuration are automatically detected during normalization by comparing the
    `_cached_fields` to the updated `fields` property.

    Examples:
        >>> from scholar_flux.api.normalization import AcademicFieldMap
        >>> field_map = AcademicFieldMap(provider_name = None, title = 'article_title', record_id='ID')
        >>> expected_result = field_map.fields | {'provider_name':'core', 'title': 'Decomposition of Political Tactics', 'record_id': 196}
        >>> result = field_map.apply(dict(provider_name='core', ID=196, article_title='Decomposition of Political Tactics'))
        >>> cached_fields = field_map._cached_fields
        >>> print(result == expected_result)
        >>> result2 = field_map.apply(dict(provider_name='core', ID=196, article_title='Decomposition of Political Tactics'))
        >>> assert cached_fields is field_map._cached_fields
        >>> assert result is not result2

    Note:
        To account for special cases, the `AcademicFieldMap` can be subclassed to perform two-step normalization to
        further process extracted elements.

        1. **Phase 1**:
            The `AcademicFieldMap` extracts nested fields for each record. This class traverses paths like
            'MedlineCitation.Article.AuthorList.Author' (PubMed) or `authorships.institutions.display_name` (OpenAlex)
            to map API-specific fields to universal parameter names
        2. **Phase 2 (Subclasses)**:
            Subclasses can reformat extracted data into finalized fields. For example, `PubMed` prepares the `authors`
            field by combining each author's 'ForeName' and 'LastName' into 'FirstName LastName'. PLOS creates the
            record URL for each article by combining the URL prefix for the website with the  `DOI` of the current
            record. The `AcademicFieldMap` defines common (yet optional) class methods to aid in the extraction and
            processing of normalized fields.

    """

    # Core identifiers
    doi: Optional[str | list[str]] = None
    url: Optional[str | list[str]] = None
    record_id: Optional[str | list[str]] = None

    # Bibliographic metadata
    title: Optional[str | list[str]] = None
    abstract: Optional[str | list[str]] = None
    authors: Optional[str | list[str]] = None

    # Publication metadata
    journal: Optional[str | list[str]] = None
    publisher: Optional[str | list[str]] = None
    year: Optional[str | list[str]] = None
    date_published: Optional[str | list[str]] = None
    date_created: Optional[str | list[str]] = None

    # Content and classification
    keywords: Optional[str | list[str]] = None
    subjects: Optional[str | list[str]] = None
    full_text: Optional[str | list[str]] = None

    # Metrics and impact
    citation_count: Optional[str | list[str]] = None

    # Access and rights
    open_access: Optional[str | list[str]] = None
    license: Optional[str | list[str]] = None

    # Document metadata
    record_type: Optional[str | list[str]] = None
    language: Optional[str | list[str]] = None
    is_retracted: Optional[str | list[str]] = None

    @classmethod
    def extract_url(
        cls,
        record: NormalizedRecordType,
        *paths: list[str | int] | str,
        pattern_delimiter: Optional[str | re.Pattern] = URL_PATTERN,
        delimiter_prefix: Optional[str] = None,
        delimiter_suffix: Optional[str] = URL_PATTERN_SUFFIX,
    ) -> Optional[str]:
        """Helper function for extracting a single, primary URL from record based on the path taken to traverse the URL.

        Args:
            record (NormalizedRecordType): The record dictionary to extract the URL from.
            *paths:
                Arbitrary positional path arguments leading to a single URL or list of URLs. Each path can be a string
                or list of keys representing the path needed to find an URL in a nested record. Defaults to the tuple
                ('url', ) if not provided, defaulting to a basic `url` lookup.
            pattern_delimiter (str | Pattern):
                Regex pattern to split URL strings. Defaults to "; *". A positive lookahead `(?=http)` is automatically
                appended to the delimiter to prevent splitting URLs mid-domain. Set to None to disable splitting.
                Note that if a re.Pattern object is provided, it will be used as is without transformation.
            delimiter_prefix (str):
                An option string appended as a prefix to each element within a pattern. This prefix is `None` by default
                but can be used to identify URLs that directly follow a specific pattern.
            delimiter_suffix (str):
                An option string appended as a suffix to each element within a pattern. This suffix is used to identify
                http` schemes (Typically associated with URLs) that may directly follow string delimited by the suffix
                separator.

        Returns:
            The first value found at any of the specified paths. Commonly a string URL,
            but could be any type depending on the data structure. Returns None if not found.

        Examples:
            >>> from scholar_flux.api.normalization import AcademicFieldMap
            >>> record = {"url": "http://example.com; http://backup.com"}
            >>> AcademicFieldMap.extract_url(record)
            # OUTPUT: 'http://example.com'

            >>> record = {"url": [{"value": "http://example.com"}]}
            >>> AcademicFieldMap.extract_url(record, ["url", 0, "value"], ["url", 0])
            # OUTPUT: 'http://example.com'

            >>> # Semicolon-delimited URLs (common in CrossRef, Springer)
            >>> record = {"url": "http://example.com; http://backup.com"}
            >>> AcademicFieldMap.extract_url(record)
            # OUTPUT: 'http://example.com'

        """
        paths = paths if paths else ("url",)
        # If URLs are delimited by the provided pattern, the pattern delimiter will be used.
        pattern = (
            try_compile(pattern_delimiter, prefix=delimiter_prefix, suffix=delimiter_suffix)
            if pattern_delimiter and isinstance(pattern_delimiter, (str, re.Pattern))
            else None
        )
        for path in paths:
            nested_element = unlist_1d(get_nested_data(record, path, verbose=False))
            url_list: Sequence = (
                re.split(pattern, nested_element)
                if isinstance(nested_element, str) and pattern
                else as_tuple(nested_element)  # nests strings, converts lists, replaces None with an empty tuple
            )
            # Retrieve the first valid URL from the sequence:
            url = next(
                (url for url in url_list if isinstance(url, str) and validate_url(url.strip(), verbose=False)), None
            )
            if url:
                return url.strip()
        return None

    @classmethod
    def extract_id(
        cls, record: NormalizedRecordType, field: str = "record_id", strip_prefix: Optional[str | re.Pattern] = None
    ) -> Optional[str]:
        """Extracts and coerces the ID from the current record into a string.

        Args:
            record (NormalizedRecordType): A normalized record dictionary before or after post-processing
            field (str): The IdType to filter for (e.g., 'arxiv_id', 'pmid', 'mag_id')
            strip_prefix (Optional[str | re.Pattern]):
                An optional prefix to remove from the identifier (e.g., 'PMC' for PMC IDs)

        Returns:
            The record ID as a string, or None if not available

        Examples:
            >>> from scholar_flux.api.normalization import AcademicFieldMap
            >>> AcademicFieldMap.extract_id({"record_id": 12345678})
            '12345678'
            >>> AcademicFieldMap.extract_id({"record_id": "mock_id:123"})
            mock_id:123'

        """
        record_id = record.get(field)
        parsed_record_id = try_none(coerce_str(record_id) if isinstance(record_id, (str, int)) else None)
        prefix_pattern = try_compile(strip_prefix, prefix="^")

        return re.sub(prefix_pattern, "", parsed_record_id) if prefix_pattern else parsed_record_id

    @classmethod
    def extract_url_id(
        cls, record: NormalizedRecordType, field: str = "record_id", strip_prefix: Optional[str | re.Pattern] = None
    ) -> Optional[str]:
        """Extracts an ID from the URL of the current record, removing a URL prefix when specified.

        Args:
            record (NormalizedRecordType): The record containing the URL ID to extract
            field (str): The field containing the ID (with or without a prefix)
            strip_prefix (Optional[str | re.Pattern]): The prefix or regex pattern to optionally remove from the URL

        Returns:
            Optional[str]:
                The ID after field extraction and the removal the string prefix, if provided. If the record field
                doesn't exist, None is returned instead.

        """
        url = record.get(field)

        if not (url and isinstance(url, str)):
            return None

        url = url.strip()
        prefix_pattern = try_compile(strip_prefix, prefix="^")

        url = re.sub(prefix_pattern, "", url) if prefix_pattern and validate_url(url, verbose=False) else url
        return url or None

    @classmethod
    def extract_year(cls, record: NormalizedRecordType, field: str = "year") -> Optional[int]:
        """Extracts the year of publication or record creation from the manuscript/record.

        Args:
            record (NormalizedRecordType): Normalized record dictionary
            field (str): The field to extract the year of publication or record creation from.

        Returns:
            Optional[int]: The year as an integer, or None if not extractable.

        Examples:
            >>> AcademicFieldMap.extract_year({"year": "2024-06-15"})
            2024
            >>> AcademicFieldMap.extract_year({"year": 2024})
            2024
            >>> AcademicFieldMap.extract_year({"year": None})
            None

        """
        year = record.get(field)
        # internally extracts a 4 digit year between 1900 and 2100
        return extract_year(year) if year else None

    @classmethod
    def reconstruct_url(cls, id: Optional[str], url: str) -> Optional[str]:
        """Reconstruct an article URL from the ID of the article.

        Useful for PLOS and PubMed URL reconstruction.

        Args:
            id (Optional[str]): The ID/DOI identifier (e.g., "10.1371/journal.pone.0123456")
            url (str): The URL prefix (e.g. f"https://journals.plos.org/plosone/article?id=")

        Returns:
            str: Reconstructed URL if ID is valid, None otherwise.

        Examples:
            >>> from scholar_flux.api.normalization import AcademicFieldMap
            >>> AcademicFieldMap.reconstruct_url(
            ...     id="10.1371/journal.pone.0123456",
            ...     url=f"https://journals.plos.org/plosone/article?id="
            ... )
            # OUTPUT: 'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0123456'
            >>> AcademicFieldMap.reconstruct_url(None, '')
            # OUTPUT: None
            >>> AcademicFieldMap.reconstruct_url("", None)
            # OUTPUT: None

        """
        # Extract primary URL if multiple exist
        id = id.strip() if isinstance(id, str) else ""
        url = url.strip() if isinstance(url, str) else ""
        if id and url:
            url = url.format(id) if "{}" in url else f"{url}{id}"
            return url if url and validate_url(url, verbose=False) else None
        return None

    @classmethod
    def normalize_doi(cls, record: NormalizedRecordType, field: str = "doi") -> Optional[str]:
        """Normalizes DOI by stripping the https://doi.org/ prefix.

        Args:
            record (NormalizedRecordType): Normalized record containing the 'doi' field to extract.
            field (str): The field to extract the record doi from.

        Returns:
            Optional[str]: Cleaned DOI string without URL prefix, or None if invalid

        Examples:
            >>> from scholar_flux.api.normalization import AcademicFieldMap
            >>> record = {'doi': 'https://doi.org/10.1234/example'}
            >>> AcademicFieldMap.normalize_doi(record)
            # OUTPUT: '10.1234/example'

        """
        doi = record.get(field)
        if isinstance(doi, str):
            cleaned = doi.replace("https://doi.org/", "").strip()
            return cleaned if cleaned else None
        return None

    @classmethod
    def extract_iso_date(cls, record: NormalizedRecordType, field: str = "date_created") -> Optional[str]:
        """Extracts and formats a date from a dictionary or strings in ISO format (%Y-%m-%d).

        Args:
            record (NormalizedRecordType):
                A normalized record having a `date_created` or similar field to extract an ISO date from.
                Note: Users can extract an ISO date from a nested dictionary field if its formatted with `year`,
                `month`, or `day`. If the nested field is a string, this method will instead attempt to parse it as an
                ISO timestamp otherwise. If the field is a datetime or date, the object will be parsed directly.
            field (str):
                The name of the field containing date information to extract.

        Returns:
            (Optional[str]): An ISO formatted date string (YYYY-MM-DD, YYYY-MM, or YYYY) or None.

        Examples:
            PubDate with Year='2025', Month='Dec', Day='19':
            Returns '2025-12-19'

            PubDate with Year='2025', Month='12':
            Returns '2025-12'

            PLOS with timestamp: '2016-12-08T00:00:00Z'
            Returns '2016-12-08'

        """

        date_data = record.get(field)

        # Accepts both string and datetime/date objects for maximum compatibility with provider and internal data.
        if isinstance(date_data, (str, datetime.datetime, datetime.date)):
            parsed_date = parse_iso_timestamp(date_data) if isinstance(date_data, str) else date_data
            return parsed_date.strftime("%Y-%m-%d") if parsed_date else None

        if isinstance(date_data, dict):
            return build_iso_date(
                year=date_data.get("Year") or date_data.get("year"),
                month=date_data.get("Month") or date_data.get("month"),
                day=date_data.get("Day") or date_data.get("day"),
            )
        return None

    @classmethod
    def extract_authors(cls, record: NormalizedRecordType, field: str = "authors") -> Optional[list[str]]:
        """Filters and cleans the author names list.

        Args:
            record (NormalizedRecordType): Normalized record with an 'authors' field.
            field (str): The field to extract the list of authors from.

        Returns:
            Optional[list[str]]: A list of non-empty author names, or None if empty

        Examples:
            >>> from scholar_flux.api.normalization import AcademicFieldMap
            >>> record = {'authors': 'Evan Doodle; Jane Doe'}
            >>> AcademicFieldMap.extract_authors(record)
            # OUTPUT: ['Evan Doodle', 'Jane Doe']
            >>> record = {'authors': ['Evan Doodle', 'Jane Noah']}
            >>> AcademicFieldMap.extract_authors(record)
            # OUTPUT: ['Evan Doodle', 'Jane Noah']
            >>> record = {'authors': [102, 203]}
            >>> AcademicFieldMap.extract_authors(record) # returns, elements aren't strings
            # OUTPUT: None

        """
        authors = record.get(field) or ""
        authors = authors.split(";") if isinstance(authors, str) else authors

        authors = [author.strip() for author in as_tuple(authors) if try_none(author) and isinstance(author, str)]
        return authors if authors else None

    @classmethod
    def extract_abstract(
        cls, record: NormalizedRecordType, strip_html: bool = False, field: str = "abstract", **kwargs
    ) -> Optional[str]:
        """Extracts and prepares the abstract for the current record.

        Args:
            record (NormalizedRecordType): Normalized record with 'abstract' already available as a field.
            strip_html (bool): Indicates whether html tags should be checked and removed if found in the abstract.
            field (str): The field where an abstract or text field can be found.
            **kwargs: Additional arguments to pass to `get_text` when stripping html elements.

        Returns:
            Optional[str]: An abstract string or None if not found or not a string/list of strings

        Example:
            >>> from scholar_flux.api.normalization import AcademicFieldMap
            >>> record = {'abstract': 'Analysis of the Placebo effect on...'}
            >>> AcademicFieldMap.extract_abstract(record)
            # OUTPUT: 'Analysis of the Placebo effect on...'

            >>> record = {'abstract': '<h1>Game theory in the technological industry.</h1><p>This study explores...</p>'}
            >>> AcademicFieldMap.extract_abstract(record, strip_html=True, separator=' ')
            # OUTPUT: 'Game theory in the technological industry. This study explores...'

        """
        abstract = record.get(field)
        if isinstance(abstract, (tuple, list)) and all(isinstance(paragraph, str) for paragraph in abstract):
            abstract = " ".join(abstract) or None

        if isinstance(abstract, str):
            return strip_html_tags(abstract, verbose=False, **kwargs) if strip_html else abstract
        return None

    @classmethod
    def extract_journal(cls, record: NormalizedRecordType, field: str = "journal") -> Optional[str]:
        """Extracts the publication journal title or a list of journal titles as a semicolon delimited string.

        Args:
            record (NormalizedRecordType): The normalized record dictionary to extract the journal field from.
            field (str): The field to extract the journal from.

        Returns:
            Optional[str]: The journal or journals of publication, joined by a semicolon, or None if not available.

        Examples:
            >>> AcademicFieldMap.extract_journal({"journal": "Nature"})
            # OUTPUT: 'Nature'
            >>> AcademicFieldMap.extract_journal({"journal": ["Nature", "Science"]})
            # OUTPUT: 'Nature; Science'
            >>> AcademicFieldMap.extract_journal({"journal": ["Nature", "", None, "Science"]})
            # OUTPUT: 'Nature; Science'

        """
        journal = record.get(field)
        return coerce_flattened_str(journal) or None

    @classmethod
    def extract_boolean_field(
        cls,
        record: NormalizedRecordType,
        field: str,
        true_values: tuple[str, ...] = ("true", "1", "yes"),
        false_values: tuple[str, ...] = ("false", "0", "no"),
        default: Optional[bool] = None,
    ) -> Optional[bool]:
        """Extracts a field's value from the current record as a boolean ('true'->True/'false'->False/'None'->None).

        Args:
            record (NormalizedRecordType): The normalized record dictionary to extract a boolean value from.
            field (str): The record field to be used for the extraction of a boolean value.
            true_values (tuple[str, ...]): Values to be mapped to True when found.
            false_values (tuple[str, ...]): Values to be mapped to false when found.
            default (Optional[bool]): The value to default to when neither True values or False values can be found.

        Returns:
            Optional[bool]:
                - True if the field appears in the list of the tuple of `true_values`
                - False if the field appears in the list of the tuple of `false_values`
                - The `default` if the observed value cannot be found within `true_values` and `false_values`

        """
        value = record.get(field)  # Maps `None` objects/strings and empty fields to None
        value = coerce_str(try_none(value))

        if value is None:
            return None

        if validate_bool_str(value, true_values):
            return True

        if validate_bool_str(value, false_values):
            return False

        return default


__all__ = ["AcademicFieldMap"]
