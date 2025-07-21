from typing import Dict, List, Any, Optional
from scholar_flux.utils import KeyDiscoverer, RecursiveDictProcessor, KeyFilter
from scholar_flux.utils import get_nested_data, as_list_1d, nested_key_exists, get_nested_data
from scholar_flux.data.base_processor import BaseDataProcessor

import re
import logging

logger = logging.getLogger(__name__)


class RecursiveDataProcessor(BaseDataProcessor):
    """
    Processes a list of raw page record dict data from the API response based on discovered record keys.
    """

    def __init__(self,
                 json_data: Optional[list[dict]] = None,
                 delimiter: Optional[str] = None,
                 value_delimiter: str = "; ",
                 ignore_keys: Optional[list[str]] = None,
                 keep_keys: Optional[list[str]] = None,
                 regex: Optional[bool] = True) -> None:
        """
        Initializes the data processor with JSON data and optional parameters for processing.
        """
        self.delimiter = delimiter
        self.value_delimiter = value_delimiter
        self.ignore_keys = ignore_keys
        self.keep_keys = keep_keys
        self.regex = regex
        self.ignore_keys = self.ignore_keys or ['.*facets.*', '.*facet-value.*']
        self.keep_keys = self.keep_keys #or ['.*abstract.*']
        self.json_data: Optional[list[dict]] = json_data
        self.key_discoverer: Optional[KeyDiscoverer] = None
        self.recursive_processor = RecursiveDictProcessor(
            delimiter=self.delimiter, object_delimiter=self.value_delimiter)
        self.load_data(json_data)

    def load_data(self, json_data: Optional[list[dict]] = None):
        json_data = json_data if json_data is not None else self.json_data
        if json_data:
            self.json_data = json_data
            self.key_discoverer = KeyDiscoverer(json_data)
        logger.debug("JSON data loaded")

    def discover_keys(self) -> Optional[dict[str, list[str]]]:
        """
        Discovers all keys within the JSON data.
        """
        return self.key_discoverer.get_all_keys() if self.key_discoverer else None

    def filter_keys(self,
                    prefix: Optional[str] = None,
                    min_length: Optional[int] = None,
                    substring: Optional[str] = None,
                    pattern: Optional[str] = None,
                    include: bool = True) -> dict[str,
                                                  list[str]]:
        """
        Filters discovered keys based on specified criteria.
        """

        if self.key_discoverer:
            return KeyFilter.filter_keys(
                self.key_discoverer.get_all_keys(),
                prefix=prefix,
                min_length=min_length,
                substring=substring,
                pattern=pattern,
                include_matches=include)
        return {}

    def process_key(self, record: dict[str, Any], key: str) -> Optional[str]:
        """
        Processes a specific key from record by joining non-None values into a string.
        """
        if not record:
            return None
        record_field = self.recursive_processor.unlist(record.get(key, []))
        if isinstance(record_field, list):
            return "; ".join(str(v) for v in record_field if v is not None)
        return str(record_field) if record_field is not None else None

    def process_text(self,
                     record_dict: dict[str,
                                       Any],
                     body_path: list[str]) -> Optional[str]:
        """
        Processes a record dictionary to extract article content, creating a processed text/abstract.
        """
        current_article = get_nested_data(record_dict, body_path)
        if isinstance(current_article, list):
            return "\n".join(p for p in current_article if p is not None)
        return str(current_article) if current_article else None

    def process_record(self,
                       record_dict: dict[str, Any],
                       header_path: list[str],
                       body_path: list[str]) -> dict[str, Any]:
        """
        Processes a record dictionary to extract record data and article content, creating a processed record dictionary with an abstract field.
        """
        # Retrieve a dict containing the fields for the current record
        record_data = self.get_nested_data(record_dict, header_path)

        # Discover and process record keys dynamically
        discovered_keys = self.discover_keys() or {}
        processed_record_dict = {
            col: self.process_key(
                record_data,
                key) for col,
            paths in discovered_keys.items() for key in paths}

        # Extract abstract text from the body path
        processed_record_dict['abstract'] = self.process_text(
            record_dict, body_path)
        return processed_record_dict

    def process_page(self,
                     parsed_records: Optional[list[dict]] = None,
                     keep_keys: Optional[list[str]] = None,
                     ignore_keys: Optional[list[str]] = None,
                     regex: Optional[bool] = None) -> list[Optional[Dict[str, str | list | None]]]:
        """
        Processes each individual record dict from the JSON data.
        """

        if parsed_records is not None:
            logger.debug("Processing next page..")
            self.load_data(parsed_records)
        elif self.json_data:
            logger.debug("Reprocessing last page..")
        else:
            raise ValueError("JSON Data has not been loaded successfully")

        keep_keys = keep_keys or self.keep_keys
        ignore_keys = ignore_keys or self.ignore_keys
        regex = regex if regex is not None else self.regex

        # Process each record in the JSON data
#        processed_record_dict_list = [
#            self.process_record(record_dict, self.recursive_processor.header_path, self.recursive_processor.body_path)
#            for record_dict in self.json_data
#            if not self.record_filter(record_dict, ignore_keys, regex)
#        ]

        # self.recursive_processor.process_dictionary()
        if not self.json_data:
            raise ValueError(f"JSON Data has not been saved successfully: {self.json_data}")

        processed_data = [
            self.recursive_processor.process_and_flatten(
                obj=record,
                exclude_keys=ignore_keys) for record in self.json_data if (
                not keep_keys or self.record_filter(
                    record_dict=record,
                    record_keys=keep_keys,
                    regex=regex)) and not (
                    self.record_filter(
                        record_dict=record,
                        record_keys=ignore_keys,
                        regex=regex))]

        logging.info(f"Total included records - {len(processed_data)}")

        # Return the list of processed record dicts
        return processed_data

    def record_filter(self,
                      record_dict: dict[str,
                                        Any],
                      record_keys: Optional[list[str]] = None,
                      regex: Optional[bool] = None) -> bool:
        """
        Filters records, using regex pattern matching, checking if any of the keys provided in the function call exist.
        """
        use_regex = regex if regex is not None else False
        if record_keys:
            logger.debug(
                f"Finding field key matches within processing data: {record_keys}")
            matches = [
                nested_key_exists(
                    record_dict,
                    key,
                    regex=use_regex) for key in record_keys] or []
            return len([match for match in matches if match]) > 0
        return False

    def get_nested_data(self, data: dict[str, Any], path: list[str]) -> Any:
        """
        Retrieve data from a nested dictionary using a list of keys as the path.
        """
        for key in path:
            data = data.get(key, {})
            if not isinstance(data, dict):
                break
        return data

#   def nested_key_exists(
#           self, data: dict[str, Any], key: str, regex: bool = False) -> bool:
#       """
#       Check if a nested key exists in a dictionary, optionally using regex pattern matching.
#       """
#       if regex:
#           pattern = re.compile(key)
#           return any(pattern.match(k) for k in data.keys())
#       return key in data.keys()


# Example usage:
if __name__ == '__main__':
    sample_json = [
        {
            "name": "John",
            "address": {
                "street": "123 Maple Street",
                "city": "Springfield",
                "state": "IL"
            },
            "phones": [
                {"type": "home", "number": "123-456-7890"},
                {"type": "work", "number": "098-765-4321"}
            ]
        }
    ]

    processor = RecursiveDataProcessor(sample_json)
    processed = processor.process_page()
    discovered_keys = processor.discover_keys()
    filtered_keys_by_prefix = processor.filter_keys(prefix='address')
    filtered_keys_by_length = processor.filter_keys(min_length=3)
    filtered_keys_by_substring = processor.filter_keys(substring='state')

    flattened_process = processor.recursive_processor.process_and_flatten(processor.json_data)
    processed_records = processor.process_page()

    print("Discovered Keys:", discovered_keys)
    print("Filtered Keys by Prefix:", filtered_keys_by_prefix)
    print("Filtered Keys by Length:", filtered_keys_by_length)
    print("Filtered Keys by Substring:", filtered_keys_by_substring)
    print("Processed Records:", processed_records)
