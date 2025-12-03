# /data/data_processor.py
"""The scholar_flux.data.data_processor implements a DataProcessor based on the schema required of the ABCDataProcessor
for processing the records and/or metadata extracted from a response. The data processor implements manual nested key
retrieval by using the list of record_keys that point to the paths of fields to extract from the passed list of nested
JSON dictionary records.

The data processor can be used to filter records based on conditions and extract nested key-value pairs within each
record to ensure that relevant records and fields from records are retained

"""
from typing import Any, Optional, Mapping
from scholar_flux.utils import get_nested_data, as_list_1d, unlist_1d, nested_key_exists, PathUtils

from scholar_flux.data import ABCDataProcessor
from scholar_flux.exceptions import DataProcessingException, DataValidationException

import logging

logger = logging.getLogger(__name__)


class DataProcessor(ABCDataProcessor):
    """Initialize the DataProcessor with explicit extraction paths and options. The DataProcessor performs the selective
    extraction os specific fields from each record within a page (list) of JSON (dictionary) records and assumes that
    the paths to extract are known beforehand.

    Args:
        record_keys: Keys to extract, as a dict of output_key to path, or a list of paths.
        ignore_keys: List of keys to ignore during processing.
        keep_keys: List of keys that records should be retained during processing.
        value_delimiter: Delimiter for joining multiple values.
        regex: Whether to use regex for ignore filtering.

    Examples
        >>> from scholar_flux.data import DataProcessor
        >>> data = [{'id':1, 'school':{'department':'NYU Department of Mathematics'}},
        >>>         {'id':2, 'school':{'department':'GSU Department of History'}},
        >>>         {'id':3, 'school':{'organization':'Pharmaceutical Research Team'}}]
        # creating a basic processor
        >>> data_processor = DataProcessor(record_keys = [['id'], ['school', 'department'], ['school', 'organization']]) # instantiating the class
        ### The process_page method can then be referenced using the processor as a callable:
        >>> result = data_processor(data) # recursively flattens and processes by default
        >>> print(result)
        # OUTPUT: [{'id': 1, 'school.department': 'NYU Department of Mathematics', 'school.organization': None},
        #          {'id': 2, 'school.department': 'GSU Department of History', 'school.organization': None},
        #          {'id': 3, 'school.department': None, 'school.organization': 'Pharmaceutical Research Team'}]
        # String paths can also be used to accomplish the same:
        >>> data_processor = DataProcessor(record_keys = ['id', 'school.department', 'school.organization']) # instantiating the class
        >>> assert data_processor.process_page(data) == result

    """

    def __init__(
        self,
        record_keys: Optional[
            dict[str | int, Any] | dict[str, Any] | list[list[str | int]] | list[list[str]] | list[str]
        ] = None,
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        value_delimiter: Optional[str] = "; ",
        regex: Optional[bool] = True,
    ) -> None:
        """Initialize the DataProcessor with explicit extraction paths and options.

        Args:
            record_keys: Keys to extract, as a dict of output_key to path, or a list of paths.
            ignore_keys: List of keys to ignore during processing.
            value_delimiter: Delimiter for joining multiple values.
            regex: Whether to use regex for ignore filtering.

        """
        super().__init__()

        self._validate_inputs(ignore_keys, keep_keys, regex, record_keys=record_keys, value_delimiter=value_delimiter)
        self.record_keys: dict[str | int, list[str | int]] = self._prepare_record_keys(record_keys) or {}
        self.ignore_keys: list[str] = ignore_keys or []
        self.keep_keys: list[str] = keep_keys or []
        self.value_delimiter = value_delimiter
        self.regex: bool = regex if regex else False

    def update_record_keys(
        self, record_keys: dict[str | int, Any] | dict[str, Any] | list[list[str | int]] | list[list[str]] | list[str]
    ) -> None:
        """A helper method for transforming and updating the current dictionary of record keys with a new list."""
        if prepared_record_keys := self._prepare_record_keys(record_keys):
            self.record_keys = prepared_record_keys
            logger.debug(f"Updated the record keys for the current {self.__class__.__name__}")

    @classmethod
    def _prepare_record_keys(
        cls,
        record_keys: Optional[
            dict[str | int, Any] | dict[str, Any] | list[list[str | int]] | list[list[str]] | list[str]
        ],
    ) -> Optional[dict[str | int, list[str | int]]]:
        """Convert record_key input into a standardized dict key value pairs. The keys represent the final key/column
        name corresponding to each nested path. Its corresponding value is a list containing each step as an element
        leading up to the final element/node in the path.

        Accepts either a list of paths or a dict of output_key to path.

        Args:
            record_keys (Optional[dict[str | int, Any] | list[list[str | int]]]): Key/path combinations indicating
                        the necessary paths to extract and, if a dictionary, the key to rename the path with.
        Returns:

        """

        try:
            if record_keys is None:
                return None
            elif isinstance(record_keys, list):
                # creates a dictionary where the joined list represents the key
                record_keys_dict: Optional[dict[str | int, list[str | int]]] = {
                    ".".join(f"{p}" for p in cls._process_record_path(record_key_path)): cls._process_record_path(
                        record_key_path
                    )
                    for record_key_path in record_keys
                    if record_key_path != []
                }

            elif isinstance(record_keys, Mapping):
                # retrieve the value in the dictionary as the full path to the element.
                # If the path is an empty list, the path will defaults to the key instead
                record_keys_dict = {key: (cls._process_record_path(path) or [key]) for key, path in record_keys.items()}

            else:
                raise TypeError(
                    "Expected a dictionary of string to path mappings or a list of lists containing paths. "
                    f"Received type ({record_keys})"
                )

            return record_keys_dict
        except (TypeError, AttributeError, ValueError) as e:
            raise DataValidationException("The record_keys attribute could not be prepared. Check the inputs: ") from e

    @classmethod
    def _process_record_path(cls, record_path: str | list) -> list:
        """Helper method that processes record paths and delimits strings into lists where applicable."""
        return record_path.split(".") if isinstance(record_path, str) else as_list_1d(record_path)

    @staticmethod
    def extract_key(
        record: dict | list | None,
        key: str | int,
        path: Optional[list[str | int]] = None,
    ) -> Optional[list]:
        """Processes a specific key from a record by retrieving the value associated with the key at the nested path.
        Depending on whether `value_delimiter` is set, the method will joining non-None values into a string using the
        delimiter. Otherwise, keys with lists as values will contain the lists un-edited.

        Args:
            record: The JSON structure (generally a nested list or dictionary) to extract the key from.
            key: The key to process within the record dictionary.

        Returns:
            list: The value found at the specified key within a dictionary nested in a list, and otherwise None.

        """

        if record is None:
            logger.debug(f"Cannot retrieve {key} as the record is None.")
            return None

        if path:
            full_path = PathUtils.path_str(path + [key])
            if isinstance(record, Mapping) and full_path in record:
                return as_list_1d(record[full_path])

        nested_record_data = (
            get_nested_data(record, path) if path and record and isinstance(record, (list, Mapping)) else record
        )

        if not isinstance(nested_record_data, Mapping):
            logger.debug(f"Cannot retrieve {key} from the following record: {record}")
            return None

        record_field = as_list_1d(nested_record_data.get(key, [])) or None
        return record_field

    def process_record(self, record_dict: dict[str | int, Any]) -> dict[str, Any]:
        """Processes a record dictionary to extract record data and article content, creating a processed record
        dictionary with an abstract field.

        Args:
        - record_dict: The dictionary containing the record data.

        Returns:
        - dict: A processed record dictionary with record keys processed and an abstract field created from the article content.

        """

        # retrieve a dict containing the fields for the current record
        if not record_dict:
            logger.debug("A record is empty: skipping,,,")
            # Simplified record data processing using dictionary comprehension

        processed_record_dict = (
            {key: self.extract_key(record_dict, path[-1], path[:-1]) for key, path in self.record_keys.items()}
            if self.record_keys
            else {}
        )

        return self.collapse_fields(processed_record_dict)

    def collapse_fields(self, processed_record_dict: dict) -> dict[str, list[str | int] | str | int]:
        """Helper method for joining lists of data into a singular string for flattening."""
        if processed_record_dict and self.value_delimiter is not None:
            return {
                k: (
                    self.value_delimiter.join(str(i) for i in field_item)
                    if field_item is not None and isinstance(field_item, (list, tuple)) and len(field_item) > 1
                    else unlist_1d(field_item)
                )
                for k, field_item in processed_record_dict.items()
            }
        return {k: unlist_1d(v) for k, v in processed_record_dict.items()}

    def process_page(
        self,
        parsed_records: list[dict[str | int, Any]],
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> list[dict]:
        """Core method of the data processor that enables the processing of lists of dictionary records to filter and
        process records based on the configuration of the current DataProcessor.

        Args:
            parsed_records (list[dict[str | int, Any]]): The records to process and/or filter
            ignore_keys (Optional[list[str]]): Optional overrides that identify records to ignore based on the absence
                                               of specific keys or regex patterns.
            keep_keys (Optional[list[str]]): Optional overrides identifying records to keep based on the absence of
                                             specific keys or regex patterns.
            regex: (Optional[bool]): Used to determine whether or not to filter records using regular expressions

        """

        keep_keys = keep_keys or self.keep_keys
        ignore_keys = ignore_keys or self.ignore_keys
        regex = regex if regex is not None else self.regex

        self._validate_inputs(
            ignore_keys, keep_keys, regex, record_keys=self.record_keys, value_delimiter=self.value_delimiter
        )

        # processes each individual record dict
        try:
            processed_record_dict_list = [
                self.process_record(record_dict)
                for record_dict in parsed_records
                if self.record_filter(record_dict, keep_keys, regex) is not False
                and self.record_filter(record_dict, ignore_keys, regex) is not True
            ]

            logger.debug(f"total included records - {len(processed_record_dict_list)}")

            # return the list of processed record dicts
            return processed_record_dict_list
        except Exception as e:
            raise DataProcessingException(f"An unexpected error occurred during data processing: {e}")

    def record_filter(
        self,
        record_dict: Mapping[str | int, Any],
        record_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> Optional[bool]:
        """Helper method that filters records using regex pattern matching, checking if any of the keys provided in the
        function call exist."""

        # return true by default if no filters are provided
        if not record_keys:
            return None

        use_regex = regex if regex is not None else False

        # search for the presence or absence of a specific key segment in the code
        logger.debug(f"Finding field key matches within processing data: {record_keys}")
        return any(key for key in record_keys if key and nested_key_exists(record_dict, key, regex=use_regex))


__all__ = ["DataProcessor"]
