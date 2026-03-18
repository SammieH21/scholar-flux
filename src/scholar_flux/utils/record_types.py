# /utils/record_types.py
"""The scholar_flux.utils.record_types module defines a set of type aliases used for processing and normalizing records.

Aliases:
    RecordType:
        A dictionary of records, either with string fields, or a combination of string and integer fields.
    NormalizedRecordType:
        A dictionary of records containing string fields only. This type is used to denote records created after
        normalization where raw records are processed and optionally remapped for consistency across different APIs.
    RecordList:
        A list of RecordTypes, typically denoting a group of dictionaries containing either string fields or a
        combination of string and integer fields. This type is generally used in `scholar_flux` when a page of records
        is extracted and is further processed.
    NormalizedRecordList:
        A list of NormalizedRecordTypes that is used to indicate groups of records after processing and normalization.
        Each record in this list is generally processed and remapped for consistency in paginated records across
        different APIs.
    MetadataType:
        An alias indicating a dictionary of metadata fields parsed from API responses. Response metadata extracted
        from APIs is typically characterized by string fields and their associated values.

"""

from typing import Any
from typing_extensions import TypeAliasType

RecordType = TypeAliasType("RecordType", dict[str, Any] | dict[str | int, Any])
RecordList = TypeAliasType("RecordList", list[dict[str, Any]] | list[dict[str | int, Any]] | list[RecordType])
NormalizedRecordType = TypeAliasType("NormalizedRecordType", dict[str, Any])
NormalizedRecordList = TypeAliasType("NormalizedRecordList", list[NormalizedRecordType])
MetadataType = TypeAliasType("MetadataType", dict[str, Any])

__all__ = ["RecordType", "NormalizedRecordType", "RecordList", "NormalizedRecordList", "MetadataType"]
