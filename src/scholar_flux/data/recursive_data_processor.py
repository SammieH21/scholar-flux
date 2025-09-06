from typing import Any, Optional
from scholar_flux.utils import KeyDiscoverer, RecursiveDictProcessor, KeyFilter
from scholar_flux.utils import nested_key_exists
from scholar_flux.data.abc_processor import ABCDataProcessor

import logging

logger = logging.getLogger(__name__)


class RecursiveDataProcessor(ABCDataProcessor):
    """
    Processes a list of raw page record dict data from the API response based on discovered record keys and
    flattens them into a list of dictionaries consisting of key value pairs that simplify the interpretation
    of the final flattened json structure.
    """

    def __init__(
        self,
        json_data: Optional[list[dict]] = None,
        value_delimiter: Optional[str] = "; ",
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = True,
        use_full_path: Optional[bool] = False,
    ) -> None:
        """
        Initializes the data processor with JSON data and optional parameters for processing.

        Args:
            json_data: The json data set to process and flatten - a list of dictionaries is expected
        """

        super().__init__()
        self.value_delimiter = value_delimiter
        self.ignore_keys = ignore_keys or None
        self.keep_keys = keep_keys or None
        self.regex = regex
        self.use_full_path = use_full_path

        self.key_discoverer: KeyDiscoverer = KeyDiscoverer([])
        self.recursive_processor = RecursiveDictProcessor(
            normalizing_delimiter=self.value_delimiter,
            object_delimiter=self.value_delimiter,
            use_full_path=use_full_path,
        )

        self.json_data: Optional[list[dict]] = json_data
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
        return self.key_discoverer.get_all_keys()

    def process_record(self, record_dict: dict[str, Any], **kwargs) -> dict[str, Any]:
        """
        Processes a record dictionary to extract record data and article content, creating a processed record dictionary with an abstract field.
        """
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

        if not self.json_data:
            raise ValueError(f"JSON Data has not been loaded successfully: {self.json_data}")

        keep_keys = keep_keys or self.keep_keys
        ignore_keys = ignore_keys or self.ignore_keys
        regex = regex if regex is not None else self.regex

        processed_json = (
            self.process_record(record_dict, exclude_keys=ignore_keys)
            for record_dict in self.json_data
            if (not keep_keys or self.record_filter(record_dict, keep_keys, regex))
            and not self.record_filter(record_dict, ignore_keys, regex)
        )

        processed_data = [record_dict for record_dict in processed_json if record_dict is not None]

        logging.info(f"Total included records - {len(processed_data)}")

        # Return the list of processed record dicts
        return processed_data

    def record_filter(
        self,
        record_dict: dict[str, Any],
        record_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> bool:
        """
        Filters records, using regex pattern matching, checking if any of the keys provided in the function call exist.
        """
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
    ) -> dict[str, list[str]]:
        """
        Filters discovered keys based on specified criteria.
        """

        return KeyFilter.filter_keys(
            self.key_discoverer.get_all_keys(),
            prefix=prefix,
            min_length=min_length,
            substring=substring,
            pattern=pattern,
            include_matches=include,
        )


if __name__ == "__main__":
    record_test_json: list[dict] = [
        {
            "authors": {"principle_investigator": "Dr. Smith", "assistant": "Jane Doe"},
            "doi": "10.1234/example.doi",
            "title": "Sample Study",
            "abstract": [
                "This is a sample abstract.",
                "keywords: 'sample', 'abstract'",
            ],
            "genre": {"subspecialty": "Neuroscience"},
            "journal": {"topic": "Sleep Research"},
        },
        {
            "authors": {"principle_investigator": "Dr. Lee", "assistant": "John Roe"},
            "dois": [{"doi": "10.5678/example2.doi"}, {"doi": "10.5681/example3.doi"}],
            "title": "Another Study",
            "abstract": "Another abstract.",
            "genre": {"subspecialty": "Psychiatry"},
            "journal": {"topic": "Dreams"},
        },
    ]
    processor = RecursiveDataProcessor(value_delimiter="; ", use_full_path=True)
    processed = processor.process_page(record_test_json)

    assert processed
