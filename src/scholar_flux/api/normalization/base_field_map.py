# scholar_flux.api.normalization.base_field_map.py
"""The scholar_flux.api.normalization.base_field_map defines a data model for normalizing API response records.

This implementation is to be used as the basis of the normalization of fields that often greatly differ in naming
convention and structure across different API implementations. Future subclasses can directly specify expected fields
and processing requirements to normalize the full range of processed records and generate a common set of named fields
that unifies API-specific record specifications into a common structure.

"""
from pydantic import Field, BaseModel, field_validator

from typing import Any, Mapping, Optional, Sequence, overload
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.utils.helpers import as_tuple
from scholar_flux.utils.record_types import RecordType, RecordList, NormalizedRecordType, NormalizedRecordList


class BaseFieldMap(BaseModel):
    """The `BaseFieldMap` is used to normalize the names of fields consistently across providers.

    This class provides a minimal implementation for mapping API-specific fields from a non-nested dictionary record
    to a common record key. It is intended to be subclassed and customized for different APIs.

    Instances of this class can be called directly to normalize a single or multiple records based on the input.
    Direct calls to instances are directly handled by `.apply()` under-the-hood.

    Methods:
        - normalize_record: Normalizes a single dictionary record
        - normalize_records: Normalizes a list of dictionary records
        - apply: Returns either a single normalized record or a list of normalized records matching the input.
        - structure: Displays a string representation of the current `BaseFieldMap` instance

    Attributes:
        provider_name (str):
            A default provider name to be assigned for all normalized records. If not provided, the field map will try to find the provider name from within each record.
        api_specific_fields (dict[str, Any]):
            Defines a dictionary of normalized field names (keys) to map to the names of fields within each dictionary record (values)
        default_field_values (dict[str, Any]):
            Indicates values that should be assigned if a field cannot be found within a record.

    """

    provider_name: str
    api_specific_fields: dict[str, Any] = Field(default_factory=dict, description="API-Specific fields")
    default_field_values: dict[str, Any] = Field(default_factory=dict, description="Optional API-Specific defaults")

    @field_validator("provider_name", mode="before")
    def validate_provider_name(cls, v: Optional[str]) -> str:
        """Transforms the `provider_name` into an empty string prior to further type validation."""
        if v is None:
            return ""

        if not isinstance(v, str):
            raise ValueError(
                f"Incorrect type received for the provider_name. Expected None or string, received {type(v)}"
            )
        return v

    @property
    def core_fields(self) -> dict[str, Any]:
        """Returns a dictionary of all core fields in the current FieldMap (excluding all API-specific fields)."""
        return {key: value for key, value in self.fields.items() if key not in self.api_specific_fields}

    @property
    def fields(self) -> dict[str, Any]:
        """Returns a representation of the current FieldMap as a dictionary."""
        field_map = self.model_dump(exclude={"api_specific_fields", "default_field_values"})
        return {key: value for key, value in field_map.items() if not key.startswith("_")} | self.api_specific_fields

    def normalize_record(
        self, record: dict, include_api_specific_fields: Optional[bool | Sequence[str]] = True
    ) -> NormalizedRecordType:
        """Maps API-specific fields in a single dictionary record to a normalized set of field names.

        Args:
            record (dict): The single, dictionary-typed record to normalize.
            include_api_specific_fields (Optional[bool | Sequence[str]]):
                A boolean indicating whether to keep or remove all API-specific fields or a sequence indicating which
                API-specific fields to keep.

        Returns:
            NormalizedRecordType: A new dictionary with normalized field names.

        Raises:
            TypeError: If the input to record is not a mapping or dictionary object.

        """
        if not isinstance(record, Mapping):
            raise TypeError(f"Expected a dictionary-typed record, but received a value of type '{type(record)}'.")

        normalized_record_fields = {
            normalized_field_name: record.get(record_key)
            for normalized_field_name, record_key in self.fields.items()
            if record_key
        }

        if "provider_name" not in normalized_record_fields:
            normalized_record_fields["provider_name"] = record.get("provider_name")

        normalized_record = self._add_defaults(normalized_record_fields)
        return self.filter_api_specific_fields(normalized_record, include_api_specific_fields)

    def normalize_records(
        self, records: RecordType | RecordList, include_api_specific_fields: Optional[bool | Sequence[str]] = True
    ) -> NormalizedRecordList:
        """Maps API-specific fields in one or more records to a normalized set of field names.

        Args:
            records (dict | RecordType | RecordList): A single dictionary record or a list of dictionary records.
            include_api_specific_fields (Optional[bool | Sequence[str]]):
                A boolean indicating whether to keep or remove all API-specific fields or a sequence indicating which
                API-specific fields to keep.

        Returns:
            NormalizedRecordList: A list of dictionaries with normalized field names.

        """
        record_list = [records] if isinstance(records, Mapping) else records
        return [self.normalize_record(record, include_api_specific_fields) for record in record_list]

    def _add_defaults(
        self, record: dict[str, Any], default_field_values: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Adds default values for fields that are missing from the current record.

        This method applies defaults only for keys that are either:
        - Not present in the record, or
        - Present but have a None value

        Args:
            record: The record to add defaults to
            default_field_values: Dictionary of default values to apply. If None, self.default_field_values is used

        Returns:
            A new dictionary with defaults merged in, without modifying the original record

        """
        default_field_values = default_field_values or self.default_field_values or {}

        filtered_defaults = {
            field: value
            for field, value in default_field_values.items()
            if record.get(field) is None or record.get(field) == ""
        }

        if not record.get("provider_name"):
            filtered_defaults["provider_name"] = default_field_values.get("provider_name") or self.provider_name or None

        return {field: None for field in self.fields} | record | filtered_defaults

    def filter_api_specific_fields(
        self, record: dict[str, Any], include_api_specific_fields: Optional[bool | Sequence[str] | set[str]] = None
    ) -> dict[str, Any]:
        """Filters API Specific parameters from the processed record."""
        if include_api_specific_fields is True or include_api_specific_fields is None or not record:
            return record

        include = set(self.core_fields.keys())

        # if Falsy, the core fields are ignored
        if isinstance(include_api_specific_fields, (Sequence, set)):
            api_specific_field_set = set(as_tuple(include_api_specific_fields))
            include = include | (self.api_specific_fields.keys() & api_specific_field_set)
        return {field: value for field, value in record.items() if field in include}

    @overload
    def apply(self, records: RecordType) -> NormalizedRecordType:
        """When calling `apply` to normalize a single record dictionary, a normalized record dictionary is returned."""
        ...

    @overload
    def apply(self, records: RecordList) -> NormalizedRecordList:
        """When calling `apply` to normalize a list of records, a list of normalized record dictionaries is returned."""
        ...

    def apply(self, records: RecordType | RecordList) -> NormalizedRecordType | NormalizedRecordList:
        """Normalizes a record or list of records by mapping API-specific field names to common fields.

        Args:
            records (RecordType | RecordList): A single dictionary record or a list of dictionary records to normalize.

        Returns:
            NormalizedRecordType: A single normalized dictionary is returned if a single record is provided.
            NormalizedRecordList: A list of normalized dictionaries is returned if a list of records is provided.

        """
        records = [] if records is None else records
        result = self.normalize_records(records) if isinstance(records, list) else self.normalize_record(records)
        return result

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the BaseFieldMap."""
        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Helper method for displaying the config in a user-friendly manner."""
        return self.structure()

    @overload
    def __call__(self, records: RecordType, *args, **kwargs) -> NormalizedRecordType:
        """When __call__ operates on a record dictionary, a normalized record dictionary is returned."""
        ...

    @overload
    def __call__(self, records: RecordList, *args, **kwargs) -> NormalizedRecordList:
        """When __call__ operates on a list of records, a list of normalized record dictionaries is returned."""
        ...

    def __call__(
        self, records: RecordType | RecordList, *args, **kwargs
    ) -> NormalizedRecordType | NormalizedRecordList:
        """Helper method that enables the current map to be used as a callable to normalize API-specific fields.

        The call delegates normalization to the `apply` method which will return a list if it receives a list and
        returns a dictionary if a single record is received, otherwise.

        Args:
            records (RecordType | RecordList): A single dictionary record or a list of dictionary records to normalize.
            *args:
                Optional positional parameters passed to `apply`. This is a `NoOp field for the `BaseFieldMap` but is
                provided for subclasses that override `apply`.
            *kwargs:
                Optional keyword parameters passed to `apply`. This is a `NoOp field for the `BaseFieldMap` but is
                provided for subclasses that override `apply`.

        Returns:
            NormalizedRecordType: A single normalized dictionary is returned if a single record is provided.
            NormalizedRecordList: A list of normalized dictionaries is returned if a list of records is provided.

        """
        return self.apply(records, *args, **kwargs)


__all__ = ["BaseFieldMap"]
