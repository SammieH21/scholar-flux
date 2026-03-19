# /data/data_extractor.py
"""The scholar_flux.data.data_extractor builds on the `BaseDataExtractor` to implement automated path extraction.

The `DataExtractor` implements dynamic record and metadata extraction when the paths are not known beforehand.

The extracted list of responses and metadata dictionaries are used in later steps prior to further response record
processing.

"""
from typing import Any, Optional, Union, overload, Mapping, Iterator
from typing_extensions import Self
from scholar_flux.exceptions import DataExtractionException
from scholar_flux.utils.helpers import filter_record_key_prefixes
from scholar_flux.utils.record_types import RecordList, RecordType, NormalizedRecordList, MetadataType

from scholar_flux.data.base_extractor import BaseDataExtractor

import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class DataExtractor(BaseDataExtractor):
    """The DataExtractor allows for the streamlined extraction of records and metadata from responses retrieved from
    APIs. This proceeds as the second stage of the response processing step where metadata and records are extracted
    from parsed responses.

    The data extractor provides two ways to identify metadata paths and record paths:

        1) manual identification: If record path or metadata_path are specified,
           then the data extractor will attempt to retrieve the metadata and records at the
           provided paths. Note that, as metadata_paths can be associated with multiple keys,
           starting from the outside dictionary, we may have to specify a dictionary containing
           keys denoting metadata variables and their paths as a list of values indicating how to
           retrieve the value. The path can also be given by a list of lists describing how to
           retrieve the last element.
        2) Dynamic identification: Uses heuristics to determine records from metadata. records
           will nearly always be defined by a list containing only dictionaries as its elements
           while the metadata will generally contain a variety of elements, some nested and others
           as integers, strings, etc. In some cases where its harder to determine, we can use
           dynamic_record_identifiers to determine whether a list containing a single nested dictionary
           is a record or metadata. For scientific purposes, its keys may contain 'abstract', 'title', 'doi',
           etc. This can be defined manually by the users if the defaults are not reliable for a given API.

    Upon initializing the class, the class can be used as a callable that returns the records and metadata
    in that order.

    Example:
        >>> from scholar_flux.data import DataExtractor
        >>> data = dict(query='specification driven development', options={'record_count':5,'response_time':'50ms'})
        >>> data['records'] = [dict(id=1, record='protocol vs.code'), dict(id=2, record='Impact of Agile')]
        >>> extractor = DataExtractor(annotate_records=False)
        >>> records, metadata = extractor(data)
        >>> print(metadata)
        # OUTPUT: {'query': 'specification driven development', 'record_count': 5, 'response_time': '50ms'}
        >>> print(records)
        # OUTPUT: [{'id': 1, 'record': 'protocol vs.code'}, {'id': 2, 'record': 'Impact of Agile'}]

    Record Annotation:
            When `annotate_records=True`, each extracted record receives two fields for
            downstream linkage after processing/flattening:

            - `_extraction_index`: Zero-based position in the extracted record list
            - `_record_id`: Content-based hash in format "hash_index" (e.g., "a1b2c3d4_0")

            These fields enable resolution back to original records when order may change
            or records are deduplicated. The hash is generated from record content excluding
            internal fields (those starting with '_'), ensuring stability across runs for
            identical content.

            Example:
                >>> extractor = DataExtractor(annotate_records=True)
                >>> records, metadata = extractor(data)
                >>> records[0]['_extraction_index']
                # OUTPUT: 0
                >>> records[0]['_record_id']
                # OUTPUT: 'a9e3e93e_0'
                >>> records[0]
                # OUTPUT: {'id': 1, 'record': 'protocol vs.code', '_extraction_index': 0, '_record_id': 'a9e3e93e_0'}

    """

    DEFAULT_DYNAMIC_RECORD_IDENTIFIERS = ("title", "doi", "abstract")  # Dict keys that commonly represent records
    DEFAULT_DYNAMIC_METADATA_IDENTIFIERS = (
        "metadata",
        "facets",
        "IdList",
    )  # Dict keys that commonly represent metadata
    EXTRACTION_INDEX_KEY = "_extraction_index"  # Optional private metadata field: Zero-based extraction position
    RECORD_ID_KEY = "_record_id"  # Optional private metadata field: ID calculated from the hash of the current record.

    def __init__(
        self,
        record_path: Optional[list] = None,
        metadata_path: Optional[list[list] | dict[str, list]] = None,
        dynamic_record_identifiers: Optional[list | tuple] = None,
        dynamic_metadata_identifiers: Optional[list | tuple] = None,
        annotate_records: Optional[bool] = None,
    ):
        """Initialize the DataExtractor with optional path overrides for metadata and records.

        Args:
            record_path (Optional[List[str]]):
                Custom path to find records in the parsed data. Contains a list of strings and rarely integers indexes
                indicating how to recursively find the list of records.
            metadata_path (List[List[str]] | Optional[Dict[str, List[str]]]):
                Identifies the paths in a dictionary associated with metadata as opposed to records. This can be a list
                of paths where each element is a list describing how to get to a terminal element.
            dynamic_record_identifiers (Optional[List[str]]):
                Helps to identify dictionary keys that only belong to records when dealing with a single element that
                would otherwise be classified as metadata.
            dynamic_metadata_identifiers (Optional[List[str]]):
                Helps to identify dictionary keys that are likely to only belong to metadata that could otherwise share
                a similar structure to a list of dictionaries, similar to what's seen with records.
            annotate_records (Optional[bool]):
                When True, adds record-identifying linkage fields to each extracted record for resolution back to
                original data after processing or flattening. Adds `_extraction_index` (position) and `_record_id`
                (content hash + index). Default is None (no annotation).

        """

        self.dynamic_record_identifiers = (
            dynamic_record_identifiers
            if dynamic_record_identifiers is not None
            else self.DEFAULT_DYNAMIC_RECORD_IDENTIFIERS
        )
        self.dynamic_metadata_identifiers = (
            dynamic_metadata_identifiers
            if dynamic_metadata_identifiers is not None
            else self.DEFAULT_DYNAMIC_METADATA_IDENTIFIERS
        )
        self.annotate_records = annotate_records

        super().__init__(record_path, metadata_path)

    @classmethod
    def _validate_dynamic_identifiers(
        cls,
        dynamic_record_identifiers: Optional[list | tuple] = None,
        dynamic_metadata_identifiers: Optional[list | tuple] = None,
    ) -> None:
        """Method used to validate the dynamic record identifiers provided to the DataExtractor prior to its later use
        in extracting metadata and records.

        Args:
            dynamic_record_identifiers (Optional[List[str | None]]): Keyword identifier indicating when singular records in a dictionary
                                                                     can be identified as such in contrast to metadata
            dynamic_metadata_identifiers (Optional[List[str | None]]): Keyword identifier indicating when record metadata keys in a dictionary
                                                                        can be identified as such in contrast to metadata
        Raises:
            DataExtractionException: Indicates an error in the DataExtractor and identifies where the inputs take on an invalid value

        """
        try:
            if dynamic_record_identifiers is not None:
                if not isinstance(dynamic_record_identifiers, (list, tuple)):
                    raise KeyError(
                        f"The dynamic record identifiers provided must be a tuple or list. Received: {type(dynamic_record_identifiers)}"
                    )
                if not all(isinstance(path, (str)) for path in dynamic_record_identifiers):
                    raise KeyError(
                        f"At least one value in the provided dynamic record identifier is not an integer or string: {dynamic_record_identifiers}"
                    )

            if dynamic_metadata_identifiers is not None:
                if not isinstance(dynamic_metadata_identifiers, (list, tuple)):
                    raise KeyError(
                        f"The dynamic metadata identifiers provided must be a tuple or list. Received: {type(dynamic_metadata_identifiers)}"
                    )
                if not all(isinstance(path, (str)) for path in dynamic_metadata_identifiers):
                    raise KeyError(
                        f"At least one value in the provided dynamic metadata identifier is not an integer or string: {dynamic_metadata_identifiers}"
                    )

        except (KeyError, TypeError) as e:
            raise DataExtractionException(
                f"Error initializing the DataExtractor: At least one of the inputs are invalid. {e}"
            ) from e
        return None

    def _validate_inputs(self) -> None:
        """Method used to validate the inputs provided to the DataExtractor prior to its later use in extracting
        metadata and records. This method operates by verifying the attributes associated with the current data
        extractor once the attributes are set.

        Note that this method is overridden so that all additional fields are validated once super().__init__(...) is
        called.

        Validated Attributes:
            record_path (Optional[List[str | None]]): The path where a list of records are located
            metadata_path (Optional[List[str | None]]): The list or dictionary of paths where metadata records are located
            dynamic_record_identifiers (Optional[List[str | None]]): Keyword identifier indicating when singular records in a dictionary
                                                                       can be identified as such in contrast to metadata
            dynamic_metadata_identifiers (Optional[List[str | None]]): Keyword identifier indicating when record metadata keys in a dictionary
                                                                        can be identified as such in contrast to metadata
        Raises:
            DataExtractionException: Indicates an error in the DataExtractor and identifies where the inputs take on an invalid value

        """
        self._validate_paths(self.record_path, self.metadata_path)
        self._validate_dynamic_identifiers(self.dynamic_record_identifiers, self.dynamic_metadata_identifiers)
        return None

    def dynamic_identification(self, parsed_page_dict: dict) -> tuple[RecordList, MetadataType]:
        """Dynamically identify and separate metadata from records. This function recursively traverses the dictionary
        and uses a heuristic to determine whether a specific record corresponds to metadata or is a list of records:
        Generally, keys associated with values corresponding to metadata will contain only lists of dictionaries On the
        other hand, nested structures containing metadata will be associated with a singular value other a dictionary of
        keys associated with a singular value that is not a list. Using this heuristic, we're able to determine metadata
        from records with a high degree of confidence.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            tuple[RecordList, MetadataType]: A tuple containing the list of record dictionaries and the metadata dictionary.

        """
        metadata: MetadataType = {}
        records: list = []

        for key, value in parsed_page_dict.items():

            if key in self.dynamic_metadata_identifiers:
                metadata[key] = value

            elif isinstance(value, dict):
                sub_records, sub_metadata = self.dynamic_identification(value)
                metadata.update(sub_metadata)
                records.extend(sub_records)

            elif isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    if len(value) == 0:
                        logger.debug(f"Element at key: {key} is empty")
                    elif len(value) > 1:  # assuming it's records if it's a list of dicts

                        records.extend(value)
                    else:
                        record = value[0]
                        if self._identify_by_key(record, self.dynamic_record_identifiers):
                            records.extend(value)
                            continue

                        sub_records, sub_metadata = self.dynamic_identification(value[0])
                        metadata.update(sub_metadata)
                        records.extend(sub_records)
            else:
                metadata[key] = value

        return records, metadata

    @staticmethod
    def _identify_by_key(record: Any, key_identifiers: list | tuple) -> bool:
        """Helper method for determining if a key exists in a dictionary.

        If a record is not a dictionary, or a key is not contained in a record dictionary,
        then this method will return False by default.
        Args:
            record (Any):
                An element in a JSON object. If a dictionary, is checked to determine
                whether any of the selected key identifiers exist within it.
            key_identifiers (list | tuple):
                Contains keys to check for. If any key exists in the record, returns True.

        """
        return all(
            [
                isinstance(record, dict),
                any(True for id_key in (key_identifiers or []) if any(id_key in record_key for record_key in record)),
            ]
        )

    def extract(self, parsed_page: Union[list[dict], dict]) -> tuple[Optional[RecordList], Optional[MetadataType]]:
        """Extract both records and metadata from the parsed page dictionary.

        Args:
            parsed_page (RecordList | dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            tuple[Optional[RecordList], Optional[MetadataType]]: A tuple containing the list of records and the metadata dictionary.

        """

        parsed_page_dict = self._prepare_page(parsed_page)

        if self.metadata_path or self.record_path:
            records = self.extract_records(parsed_page_dict)
            metadata = self.extract_metadata(parsed_page_dict)
        else:
            records, metadata = self.dynamic_identification(parsed_page_dict)

        if self.annotate_records and records:
            records = self._annotate_records(records)

        return records, metadata

    @classmethod
    def _annotate_records(
        cls,
        records: RecordList,
        start: int = 0,
    ) -> RecordList:
        """Annotate records with extraction index and content-based ID.

        Adds `_extraction_index` and `_record_id` to each record for:
        - Resolution back to original non-flattened data after processing
        - Idempotent identification across runs (content-based hash)

        Args:
            records (RecordList): A list of extracted records to annotate.
            start (int):
                Indicates the starting index that annotation should use when assigning `_extraction_index` keys. The
                `start` parameter is passed directly to `enumerate` and is useful for continuing enumeration across
                multiple calls.

        Returns:
            RecordList: Records with annotation fields added

        """
        for idx, record in enumerate(records, start=start):
            if isinstance(record, dict):
                record[cls.EXTRACTION_INDEX_KEY] = idx
                record[cls.RECORD_ID_KEY] = cls._generate_record_id(record, idx)

        return records

    @classmethod
    def _generate_record_id(cls, record: RecordType, index: int) -> str:
        """Generates a stable, content-based record ID for idempotency.

        Creates a deterministic ID by hashing sorted record content. The same
        record content will produce the same ID across different runs.

        Args:
            record (RecordType): Record to generate ID for
            index (int): Extraction index (used as fallback component)

        Returns:
            str: Format "hash_index" - 16-char content hash + extraction index.
                 Falls back to "idx_index" for non-serializable content.

        """
        content = cls.strip_annotations(record)

        try:
            stable_str = json.dumps(content, sort_keys=True, default=str)
            content_hash = hashlib.md5(stable_str.encode("utf-8")).hexdigest()[:16]
        except (TypeError, ValueError):
            # Fall back to index-only on errors
            content_hash = "idx"

        return f"{content_hash}_{index}"

    @classmethod
    @overload
    def strip_annotations(cls, records: RecordType) -> RecordType:
        """When `strip_annotations` is called on a single record, internal annotations are stripped."""
        ...

    @classmethod
    @overload
    def strip_annotations(cls, records: NormalizedRecordList) -> NormalizedRecordList:
        """When `strip_annotations` is called on a normalized record, internal annotations are stripped."""
        ...

    @classmethod
    @overload
    def strip_annotations(cls, records: RecordList) -> RecordList:
        """When `strip_annotations` is called on a record list, each record is stripped, returning a list."""
        ...

    @classmethod
    @overload
    def strip_annotations(cls, records: None) -> None:
        """When `strip_annotations` is called and a record is None, None is returned."""
        ...

    @classmethod
    def strip_annotations(
        cls,
        records: Optional[Union[RecordType, RecordList, NormalizedRecordList]],
    ) -> Optional[Union[RecordType, RecordList, NormalizedRecordList]]:
        """Removes metadata annotations from records by filtering out keys prefixed with underscore.

        This method creates clean copies of records without internal pipeline metadata fields that may be added during
        (e.g., '_extraction_index', '_record_id') processing when record annotation is enabled.

        Args:
            records (RecordType | RecordList):
                A single dictionary record or a list of dictionary records to clean. Records should contain dictionary
                elements with string keys.

        Returns:
            RecordType: A new dictionary with annotation fields removed if input is a single record.
            RecordList: A new list of dictionaries with annotation fields removed if input is a list.

        Note:
            The original records are not modified. This method instead return a new dictionary or a new list of
            dictionaries  with only non-annotation fields preserved.

        """
        if records is None:
            return None
        if not isinstance(records, (list, Iterator, Mapping)):
            raise TypeError(
                "Expected a dict or list of dicts to strip metadata annotations from, but received type "
                f"{type(records)}."
            )
        if isinstance(records, (Iterator, list)):
            return [
                filter_record_key_prefixes(record if record is not None else {}, prefix="_", invert=False)
                for record in records
            ]
        return filter_record_key_prefixes(records, prefix="_", invert=False)

    @classmethod
    def update(cls, data_extractor: BaseDataExtractor, **data_extractor_kwargs: Any) -> Self:
        """Helper method for creating a new DataExtractor instance, replacing only the specified components.

        Args:
            data_extractor (Self): A previously created DataExtractor instance
            **data_extractor_kwargs:
                Keyword arguments used to replace components of the DataExtractor. Unspecified fields from the previous
                `DataExtractor` remain unchanged.
        Returns:
            DataExtractor: A new data extractor instance with the specified parameter updates

        """
        if not isinstance(data_extractor, BaseDataExtractor):
            raise TypeError(
                "Expected a BaseDataExtractor or subclass to perform parameter updates. Received type "
                f"{type(data_extractor)}"
            )
        return cls(
            record_path=data_extractor_kwargs.get("record_path", data_extractor.record_path),
            metadata_path=data_extractor_kwargs.get("metadata_path", data_extractor.metadata_path),
            dynamic_record_identifiers=data_extractor_kwargs.get(
                "dynamic_record_identifiers", getattr(data_extractor, "dynamic_record_identifiers", None)
            ),
            dynamic_metadata_identifiers=data_extractor_kwargs.get(
                "dynamic_metadata_identifiers", getattr(data_extractor, "dynamic_metadata_identifiers", None)
            ),
            annotate_records=data_extractor_kwargs.get(
                "annotate_records", getattr(data_extractor, "annotate_records", False)
            ),
        )


__all__ = ["DataExtractor"]
