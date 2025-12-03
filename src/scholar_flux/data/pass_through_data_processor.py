# /data/pass_through_data_processor.py
"""The scholar_flux.data.pass_through_data_processor implements a PassThroughDataProcessor based on the schema required
of the ABCDataProcessor for processing the records and/or metadata extracted from a response.

The pass through data processor is designed for simplicity, allowing end-users to return extracted records as is and
also filter records based on conditions and extract nested key-value pairs within each record if specified.

"""
from typing import Any, Optional
from scholar_flux.utils import nested_key_exists

from scholar_flux.data import ABCDataProcessor
from scholar_flux.exceptions import DataProcessingException

import logging

logger = logging.getLogger(__name__)


class PassThroughDataProcessor(ABCDataProcessor):
    """A basic data processor that retains all valid records without modification unless a specific filter for JSON keys
    are specified.

    Unlike the DataProcessor, this specific implementation will not flatten records. Instead all filtered and selected
    records will retain their original nested structure.

    """

    def __init__(
        self,
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = True,
    ) -> None:
        """Initialize the PassThroughDataProcessor with explicit extraction paths and options.

        Args:
            ignore_keys: List of keys to ignore during processing.
            keep_keys: List of keys that records should contain during processing.
            value_delimiter: Delimiter for joining multiple values.
            regex: Whether to use regex for ignore filtering.

        """
        super().__init__()

        self._validate_inputs(ignore_keys, keep_keys, regex)
        self.ignore_keys: list[str] = ignore_keys or []
        self.keep_keys: list[str] = keep_keys or []
        self.regex: bool = regex if regex is not None else False

    def process_record(self, record_dict: dict[str | int, Any]) -> dict[str | int, Any]:
        """A no-op method retained for to maintain a similar interface as other DataProcessor implementations.

        Args:
        - record_dict: The dictionary containing the record data.

        Returns:
        - dict: The original processed dictionary

        """
        return record_dict or {}

    def process_page(
        self,
        parsed_records: list[dict[str | int, Any]],
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> list[dict]:
        """Processes and returns each record as is if filtering the final list of records by key is not enabled."""

        keep_keys = keep_keys or self.keep_keys
        ignore_keys = ignore_keys or self.ignore_keys
        regex = regex if regex is not None else self.regex

        self._validate_inputs(ignore_keys, keep_keys, regex)

        try:
            # processes each individual record dict
            processed_record_dict_list = [
                self.process_record(record_dict)
                for record_dict in parsed_records
                if self.record_filter(record_dict, keep_keys, regex) is not False
                and self.record_filter(record_dict, ignore_keys, regex) is not True
            ]

            logger.info(f"total included records - {len(processed_record_dict_list)}")

            # return the list of processed record dicts
            return processed_record_dict_list
        except Exception as e:
            raise DataProcessingException(f"An unexpected error occurred during data processing: {e}")

    def record_filter(
        self, record_dict: dict[str | int, Any], record_keys: Optional[list[str]] = None, regex: Optional[bool] = None
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


__all__ = ["PassThroughDataProcessor"]
