# /data/recursive_data_processor.py
"""The scholar_flux.data.recursive_data_processor implements the RecursiveDataProcessor that implements the dynamic, and
automatic recursive retrieval of nested key-data pairs from listed dictionary records.

The data processor can be used to flatten and filter records based on conditions and extract nested data for each record
in the response.

"""
from typing import Any, Optional
from scholar_flux.utils import KeyDiscoverer, RecursiveJsonProcessor, KeyFilter
from scholar_flux.utils import nested_key_exists
from scholar_flux.data.abc_processor import ABCDataProcessor

from scholar_flux.exceptions import DataProcessingException, DataValidationException

import threading
import logging

logger = logging.getLogger(__name__)


class RecursiveDataProcessor(ABCDataProcessor):
    """Processes a list of raw page record dict data from the API response based on discovered record keys and flattens
    them into a list of dictionaries consisting of key value pairs that simplify the interpretation of the final
    flattened json structure.

    Example:
        >>> from scholar_flux.data import RecursiveDataProcessor
        >>> data = [{'id':1, 'a':{'b':'c'}}, {'id':2, 'b':{'f':'e'}}, {'id':2, 'c':{'h':'g'}}]
        # creating a basic processor
        >>> recursive_data_processor = RecursiveDataProcessor() # instantiating the class
        ### The process_page method can then be referenced using the processor as a callable:
        >>> result = recursive_data_processor(data) # recursively flattens and processes by default
        >>> print(result)
        # OUTPUT: [{'id': '1', 'b': 'c'}, {'id': '2', 'f': 'e'}, {'id': '2', 'h': 'g'}]
            # To identify the full nested location of record:
        >>> recursive_data_processor = RecursiveDataProcessor(use_full_path=True) # instantiating the class
        >>> result = recursive_data_processor(data) # recursively flattens and processes by default
        >>> print(result)
        # OUTPUT: [{'id': '1', 'a.b': 'c'}, {'id': '2', 'b.f': 'e'}, {'id': '2', 'c.h': 'g'}]

    """

    def __init__(
        self,
        json_data: Optional[list[dict]] = None,
        value_delimiter: Optional[str] = "; ",
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = True,
        use_full_path: Optional[bool] = True,
    ) -> None:
        """Initializes the data processor with JSON data and optional parameters for processing.

        Args:
            json_data (list[dict]): The json data set to process and flatten - a list of dictionaries is expected
            value_delimiter (Optional[str]): Indicates whether or not to join values found at terminal paths
            ignore_keys (Optional[list[str]]): Determines records that should be omitted based on whether each
                                               record contains a key or substring. (off by default)
            keep_keys (Optional[list[str]]): Indicates whether or not to keep a record if the key is present.
                                             (off by default)
            regex (Optional[bool]): Determines whether to use regex filtering for filtering records based on the
                                    presence or absence of specific keywords
            use_full_path (Optional[bool]): Determines whether or not to keep the full path for the json record key.
                                            If False, the path is shortened, keeping the last key or set of keys
                                            while preventing name collisions.

        """

        super().__init__()
        self._validate_inputs(ignore_keys, keep_keys, regex)

        self.value_delimiter = value_delimiter
        self.ignore_keys = ignore_keys
        self.keep_keys = keep_keys
        self.regex = regex
        self.use_full_path = use_full_path

        self.key_discoverer: KeyDiscoverer = KeyDiscoverer([])
        self.recursive_processor = RecursiveJsonProcessor(
            normalizing_delimiter=self.value_delimiter,
            object_delimiter=self.value_delimiter,
            use_full_path=use_full_path,
        )

        self.json_data: Optional[list[dict]] = json_data
        self.load_data(json_data)
        self.lock = threading.Lock()

    def load_data(self, json_data: Optional[list[dict]] = None):
        """Attempts to load a data dictionary or list, contingent of it having at least one non-missing record to load
        from. If `json_data` is missing, or the json input is equal to the current `json_data` attribute, then the
        json_data attribute will not be updated from the json input.

        Args:
            json_data (Optional[list[dict]]) The json data to be loaded as an attribute
        Returns:
            bool: Indicates whether the data was successfully loaded (True) or not (False)

        """
        try:
            json_data = json_data if json_data is not None else self.json_data
            if json_data:
                self.json_data = json_data
                self.key_discoverer = KeyDiscoverer(json_data)
            logger.debug("JSON data loaded")
        except Exception as e:
            raise DataValidationException(
                f"The JSON data of type {type(self.json_data)} could not be successfully " f"processed and loaded: {e}"
            )

    def discover_keys(self) -> Optional[dict[str, list[str]]]:
        """Discovers all keys within the JSON data."""
        return self.key_discoverer.get_all_keys()

    def process_record(self, record_dict: dict[str, Any], **kwargs) -> dict[str, Any]:
        """Processes a record dictionary to extract record data and article content, creating a processed record
        dictionary with an abstract field."""
        # Retrieve a dict containing the fields for the current record
        if not record_dict:
            return {}

        return self.recursive_processor.process_and_flatten(obj=record_dict, **kwargs) or {}

    def process_page(
        self,
        parsed_records: Optional[list[dict]] = None,
        keep_keys: Optional[list[str]] = None,
        ignore_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> list[dict]:
        """Processes each individual record dict from the JSON data."""

        if parsed_records is not None:
            logger.debug("Processing next page..")
            self.load_data(parsed_records)
        elif self.json_data:
            logger.debug("Reprocessing last page..")
        else:
            raise DataValidationException(f"JSON Data has not been loaded successfully: {self.json_data}")

        if not self.json_data:
            raise DataValidationException(f"JSON Data has not been loaded successfully: {self.json_data}")

        keep_keys = keep_keys or self.keep_keys
        ignore_keys = ignore_keys or self.ignore_keys
        regex = regex if regex is not None else self.regex

        self._validate_inputs(ignore_keys, keep_keys, regex)

        try:
            processed_json = (
                self.process_record(record_dict, exclude_keys=ignore_keys)
                for record_dict in self.json_data
                if (not keep_keys or self.record_filter(record_dict, keep_keys, regex))
                and not self.record_filter(record_dict, ignore_keys, regex)
            )

            processed_data = [record_dict for record_dict in processed_json if record_dict is not None]

            logger.info(f"Total included records - {len(processed_data)}")

            # Return the list of processed record dicts
            return processed_data
        except Exception as e:
            raise DataProcessingException(f"An unexpected error occurred during data processing: {e}")

    def record_filter(
        self,
        record_dict: dict[str, Any],
        record_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> bool:
        """Filters records, using regex pattern matching, checking if any of the keys provided in the function call
        exist."""
        use_regex = regex if regex is not None else False
        if record_keys:
            logger.debug(f"Finding field key matches within processing data: {record_keys}")
            matches = [nested_key_exists(record_dict, key, regex=use_regex) for key in record_keys] or []
            return len([match for match in matches if match]) > 0
        return False

    def filter_keys(
        self,
        prefix: Optional[str] = None,
        min_length: Optional[int] = None,
        substring: Optional[str] = None,
        pattern: Optional[str] = None,
        include: bool = True,
        **kwargs,
    ) -> dict[str, list[str]]:
        """Filters discovered keys based on specified criteria."""

        return KeyFilter.filter_keys(
            self.key_discoverer.get_all_keys(),
            prefix=prefix,
            min_length=min_length,
            substring=substring,
            pattern=pattern,
            include_matches=include,
            **kwargs,
        )

    def __call__(self, *args, **kwargs) -> list[dict]:
        """Convenience method that calls process_page while also locking the class for processing while a single page is
        processed.

        Useful in a threading context where multiple SearchCoordinators may be using the same RecursiveDataProcessor.

        """
        with self.lock:
            return self.process_page(*args, **kwargs)


__all__ = ["RecursiveDataProcessor"]
