# scholar_flux.api.normalization.base_field_map.py
"""The scholar_flux.api.normalization.base_field_map defines a data model for normalizing API response records.

This implementation is to be used as the basis of the normalization of fields that often greatly differ in naming
convention and structure across different API implementations. Future subclasses can directly specify expected fields
and processing requirements to normalize the full range of processed records and generate a common set of named fields
that unifies API-specific record specifications into a common structure.

"""
from pydantic import Field, BaseModel, field_validator

from typing import Any, Optional, Mapping
from scholar_flux.utils.repr_utils import generate_repr


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
    def fields(self) -> dict[str, Any]:
        """Prints a representation of the current FieldMap as a dictionary."""
        field_map = self.model_dump(exclude={"api_specific_fields", "default_field_values"})
        return {key: value for key, value in field_map.items() if not key.startswith("_")} | self.api_specific_fields

    def normalize_record(self, record: dict) -> dict[str, Any]:
        """Maps API-specific fields in a single dictionary record to a normalized set of field names.

        Args:
            record: The single, dictionary-typed record to normalize.

        Returns:
            A new dictionary with normalized field names.

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
        return normalized_record

    def normalize_records(self, records: dict | list[dict]) -> list[dict[str, Any]]:
        """Maps API-specific fields in one or more records to a normalized set of field names.

        Args:
            records: A single dictionary record or a list of dictionary records.

        Returns:
            A list of dictionaries with normalized field names.

        """
        record_list = [records] if isinstance(records, Mapping) else records
        return [self.normalize_record(record) for record in record_list]

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

    def apply(self, records: dict | list[dict]) -> dict[str, Any] | list[dict[str, Any]]:
        """Normalizes a record or list of records by mapping API-specific field names to common fields.

        Args:
            records: A single dictionary record or a list of dictionary records.

        Returns:
            A single, normalized dictionary is returned if a single record is provided otherwise,
            if a list of records is provided, a list of normalized dictionaries is returned.

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

    def __call__(self, *args, **kwargs) -> dict[str, Any] | list[dict[str, Any]]:
        """Helper method that enables the current map to be used as a callable to normalize API-specific fields.

        The call delegates normalization to the `apply` method which will return a list if it receives a list and
        returns a dictionary if a single record is received, otherwise.

        """
        return self.apply(*args, **kwargs)


__all__ = ["BaseFieldMap"]
