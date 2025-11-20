# scholar_flux.api.normalization.academic_field_map.py
"""The scholar_flux.api.normalization.academic_field_map defines a data model for normalizing API response records.

This implementation is to be used as the basis of the normalization of fields that often greatly differ in naming
convention and structure across different API implementations. Future subclasses can directly specify expected fields
and processing requirements to normalize the full range of processed records and generate a common set of named fields
that unifies API-specific record specifications into a common structure.

"""
from pydantic import PrivateAttr
from typing import Any, Optional, Mapping
from functools import cached_property
from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.data.normalizing_data_processor import DataProcessor, NormalizingDataProcessor
from scholar_flux.exceptions import RecordNormalizationException, DataProcessingException
import logging

logger = logging.getLogger(__name__)


class AcademicFieldMap(BaseFieldMap):
    """A field map implementation that builds upon the original BaseFieldMap to customize academic record normalization.
    Class used to normalize the names of fields consistently across provider


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
    doi: Optional[str] = None
    url: Optional[str] = None
    record_id: Optional[str] = None

    # Bibliographic metadata
    title: Optional[str] = None
    abstract: Optional[str] = None
    authors: Optional[str] = None

    # Publication metadata
    journal: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[str] = None
    date_published: Optional[str] = None
    date_created: Optional[str] = None

    # Content and classification
    keywords: Optional[str] = None
    subjects: Optional[str] = None
    full_text: Optional[str] = None

    # Metrics and impact
    citation_count: Optional[str] = None

    # Access and rights
    open_access: Optional[str] = None
    license: Optional[str] = None

    # Document metadata
    record_type: Optional[str] = None
    language: Optional[str] = None
    _processor: NormalizingDataProcessor = PrivateAttr(default_factory=NormalizingDataProcessor)

    @cached_property
    def _cached_fields(self) -> dict[str, Any]:
        """A cached property used to snapshot the dictionary of field mappings used by the current map on instantiation.

        This cached private property is assigned the initial value of the `fields` property on the first access of the
        `AcademicFieldMap` and used internally to create a cache of the current mapping of academic, API-specific field
        names to a common set of field names used to normalize academic records.

        This property is later compared against the current `fields` property to determine if the data processor of the
        current map needs to be regenerated before mapping API-specific parameters to the universal set
        of fields used to normalize academic records into a common structure.

        **Note**: This implementation also accounts for when individual fields of the current AcademicFieldMap are
        changed directly by the end-user.

        """
        return self.fields

    def _refresh_cached_fields(self) -> None:
        """Helper method for invalidating and refreshing the `_cached_fields` property"""
        if "_cached_fields" in self.__dict__:
            del self._cached_fields

    @property
    def processor(self) -> NormalizingDataProcessor:
        """Generates a NormalizingDataProcessor using the current set of assigned field names.

        Note that if a processor does not already exist or if the schema is changed, The data processor is recreated
        with the updated set of fields.

        """
        if not self._processor.record_keys or self.fields != self._cached_fields:
            self._update_record_keys()
        return self._processor

    @processor.setter
    def processor(self, processor: NormalizingDataProcessor):
        """Generates a NormalizingDataProcessor using the current set of assigned field names."""
        if not isinstance(processor, DataProcessor):
            err = f"Expected a DataProcessor, but received a variable of {type(processor)}"
            logger.error(err)
            raise RecordNormalizationException(err)
        self._processor = processor

    def _update_record_keys(self) -> None:
        """Updates the record keys of the NormalizingDataProcessor using the current dictionary of field mappings."""
        processing_fields = {
            field: record_key for field, record_key in self.fields.items() if record_key and field != "provider_name"
        }

        # if provider name is None/an empty string, replace with
        if not self.provider_name:
            processing_fields["provider_name"] = "provider_name"

        self._processor.update_record_keys(processing_fields)
        self._refresh_cached_fields()

    def normalize_record(self, record: dict) -> dict[str, Any]:
        """Maps API-specific fields in dictionaries of processed records to a normalized set of field names."""

        if record is None:
            return {}

        if not isinstance(record, dict):
            err = f"Expected record to be of type `dict`, but received a variable of {type(record)}"
            logger.error(err)
            raise RecordNormalizationException(err)

        normalized_record = self.processor.process_record(record)
        normalized_record = self._add_defaults(normalized_record)

        return normalized_record

    def normalize_records(self, records: dict | list[dict]) -> list[dict[str, Any]]:
        """Maps API-specific fields within a processed record list to create a new, normalized record list."""

        if records is None:
            return []

        record_list = [records] if isinstance(records, Mapping) else records

        if not isinstance(record_list, (list, Mapping)):
            err = f"Expected the record list to be of type `list`, but received a variable of {type(record_list)}"
            logger.error(err)
            raise RecordNormalizationException(err)

        try:
            normalized_record_list = self.processor(record_list)
        except DataProcessingException as e:
            err = f"Encountered an error during the data processing step of record normalization: {e}"
            logger.error(err)
            raise RecordNormalizationException(err)

        return [self._add_defaults(normalized_record) for normalized_record in normalized_record_list]


__all__ = ["AcademicFieldMap"]
