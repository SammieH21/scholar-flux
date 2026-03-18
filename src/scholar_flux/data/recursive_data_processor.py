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
from scholar_flux.utils.record_types import RecordType, RecordList

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
        value_delimiter: Optional[str] = None,
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

        self.json_data = None
        self.load_data(json_data)
        self.lock = threading.Lock()

    @property
    def json_data(self) -> Optional[RecordList]:
        """A list of dictionary-based records to further process."""
        return self._json_data

    @json_data.setter
    def json_data(self, data: Optional[RecordType | RecordList]) -> None:
        """A list of dictionary-based records to further process."""
        if isinstance(data, dict):
            data = [data]

        self._validate_json_data(data)
        self._json_data = data

    def load_data(self, json_data: Optional[RecordType | RecordList] = None) -> bool:
        """Attempts to load a data dictionary or list, contingent on the input having at least one non-missing record.

        If `json_data` is missing, or the json input is equal to the current `json_data` attribute, then the
        json_data attribute will not be updated from the json input.

        Args:
            json_data (Optional[RecordType | RecordList]): The json data to be loaded as an attribute.

        Returns:
            bool: Indicates whether the data was successfully loaded (True) or not (False).

        """
        if json_data is None and self.json_data is None:
            return False

        try:

            if json_data is not None and json_data != self.json_data:
                if self.json_data is not None:
                    logger.debug("Updating JSON data...")
                self.json_data = json_data

            self.key_discoverer = KeyDiscoverer(self.json_data)

            logger.debug("JSON data loaded.")
            return True
        except Exception as e:
            raise DataValidationException(f"The JSON data could not be successfully loaded and processed: {e}")

    def discover_keys(self) -> Optional[dict[str, list[str]]]:
        """Discovers all keys within the JSON data."""
        return self.key_discoverer.get_all_keys()

    def process_record(self, record_dict: RecordType, **kwargs: Any) -> RecordType:
        """Processes and flattens record dictionary, extracting record data and article content in the process."""
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
        try:
            if parsed_records is not None:
                logger.debug("Processing next page...")
                self.load_data(parsed_records)
            elif self.json_data:
                logger.debug("Reprocessing last page...")

            if self.json_data is None:
                raise DataValidationException("A valid JSON dictionary could not be successfully loaded.")

            keep_keys = keep_keys or self.keep_keys
            ignore_keys = ignore_keys or self.ignore_keys
            regex = regex if regex is not None else self.regex

            self._validate_inputs(ignore_keys, keep_keys, regex)

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
        except DataProcessingException:
            raise
        except Exception as e:
            raise DataProcessingException(f"An unexpected error occurred during data processing: {e}")

    @classmethod
    def record_filter(
        cls,
        record_dict: RecordType,
        record_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> bool:
        """Indicates if the current record contains any of the keys."""
        if not record_keys:
            return False

        use_regex = regex if regex is not None else False
        logger.debug(f"Finding field key matches within processing data: {record_keys}")
        matches = (nested_key_exists(record_dict, key, regex=use_regex) for key in record_keys)
        return any(matches)

    def filter_keys(
        self,
        prefix: Optional[str] = None,
        min_length: Optional[int] = None,
        substring: Optional[str] = None,
        pattern: Optional[str] = None,
        include: bool = True,
        **kwargs: Any,
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

    def __call__(self, *args: Any, **kwargs: Any) -> list[dict]:
        """Convenience method that applies a thread lock and processes a single page of JSON data via `.process_page()`.

        Useful in a threading context where multiple SearchCoordinators may be using the same `RecursiveDataProcessor`.

        """
        with self.lock:
            return self.process_page(*args, **kwargs)


__all__ = ["RecursiveDataProcessor"]
