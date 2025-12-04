# scholar_flux.api.normalization.academic_field_map.py
"""The scholar_flux.api.normalization.academic_field_map implements the `AcademicFieldMap` for scholarly record
normalization.

This implementation subclasses the `NormalizingFieldMap` class for use in academic record normalization by defining
additional combinations of fields that apply solely to academic APIs and databases.

"""
from typing import Optional
from scholar_flux.api.normalization.normalizing_field_map import NormalizingFieldMap


class AcademicFieldMap(NormalizingFieldMap):
    """A field map implementation that builds on the `NormalizingFieldMap` to customize academic record normalization.

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

    """

    # Core identifiers
    provider_name: str = ""
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


__all__ = ["AcademicFieldMap"]
