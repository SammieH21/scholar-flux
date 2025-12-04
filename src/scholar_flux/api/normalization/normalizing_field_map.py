# scholar_flux.api.normalization.normalizing_field_map.py
"""The scholar_flux.api.normalization.normalizing_field_map implements the `NormalizingFieldMap` for complex record
normalization scenarios.

This class builds on the `BaseFieldMap`, using a `NormalizingDataProcessor` to handle nested field traversal and
scenarios where fields may be differently named in different records from the same API provider. The
`NormalizingFieldMap` can be subclassed with specialized field names for validated normalization.

"""
from pydantic import PrivateAttr
from typing import Any, Mapping
from functools import cached_property
from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.data.normalizing_data_processor import DataProcessor, NormalizingDataProcessor
from scholar_flux.exceptions import RecordNormalizationException, DataProcessingException
import logging

logger = logging.getLogger(__name__)


class NormalizingFieldMap(BaseFieldMap):
    """A field map implementation that builds upon the original BaseFieldMap to recursively find and retrieve nested
    JSON elements from records with automated index processing and path-guided traversal.

    During normalization, the `NormalizingFieldMap.fields` property returns all subclassed field mappings as a flattened
    dictionary (excluding private fields prefixed with underscores). Both simple and nested API-specific
    field names are matched and mapped to universal field names.

    Any changes to the instance configuration are automatically detected during normalization by comparing the
    `_cached_fields` to the updated `fields` property.

    Examples:
        >>> from scholar_flux.api.normalization.normalizing_field_map import NormalizingFieldMap
        >>> field_map = NormalizingFieldMap(provider_name = None, api_specific_fields=dict(title = 'article_title', record_id='ID'))
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
    _processor: NormalizingDataProcessor = PrivateAttr(default_factory=NormalizingDataProcessor)

    @cached_property
    def _cached_fields(self) -> dict[str, Any]:
        """A cached property used to snapshot the dictionary of field mappings used by the current map on instantiation.

        This cached private property is assigned the initial value of the `fields` property on the first access of the
        `NormalizingFieldMap` and used internally to create a cache of the current mapping of API-specific field
        names to a common set of field names used to normalize both universal records common to a domain as well as
        API-specific records.

        This property is later compared against the current `fields` property to determine if the data processor of the
        current map needs to be regenerated before mapping API-specific parameters to the universal set
        of fields used to normalize records into a common structure.

        **Note**: This implementation also accounts for when individual fields of the current NormalizingFieldMap are
        changed directly by the end-user.

        """
        return self.fields

    def _refresh_cached_fields(self) -> None:
        """Helper method for invalidating and refreshing the `_cached_fields` property."""
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
            field: record_key
            for field, record_key in self.fields.items()
            if record_key and isinstance(record_key, str) and field != "provider_name"
        }

        processing_fields = processing_fields | {
            self._index_key(field, i): record_key
            for field, record_key_list in self.fields.items()
            if isinstance(record_key_list, list)
            for i, record_key in enumerate(record_key_list)
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
        normalized_record = self._add_defaults(self._resolve_fallbacks(normalized_record))

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

        return [
            self._add_defaults(self._resolve_fallbacks(normalized_record))
            for normalized_record in normalized_record_list
        ]

    @classmethod
    def _index_key(cls, field: str, index: int, suffix: str = "_fallback_") -> str:
        """Adds a simple index to the current field name to distinguish it for later retrieval."""
        if index == 0:
            return field
        return f"{field}{suffix}{index}"

    def _resolve_fallbacks(self, record: dict[str, Any]) -> dict[str, Any]:
        """Resolve universal fields with lists of record keys that may vary depending on the record type."""
        record_keys = self.fields
        for field, record_key_list in record_keys.items():
            if not isinstance(record_key_list, list):
                continue
            for i, _ in enumerate(record_key_list):
                current_field_key = self._index_key(field, i) if i > 0 else field
                value = record.pop(current_field_key, None) if i > 0 else record.get(field)

                if record.get(field) is None and i > 0 and value is not None:
                    record[field] = value
        return record


__all__ = ["NormalizingFieldMap"]
