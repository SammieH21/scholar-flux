from typing import Any, Optional, Union
from scholar_flux.utils import PathNodeIndex, ProcessingPath, PathDiscoverer, as_list_1d
from scholar_flux.data.abc_processor import ABCDataProcessor

# from scholar_flux.data.recursive_data_processor import RecursiveDataProcessor
# from scholar_flux.data.dynamic_data_processor import DynamicDataProcessor
import re
import logging


logger = logging.getLogger(__name__)


class PathDataProcessor(ABCDataProcessor):
    """
    Uses custom path processing to process a list of raw page record dict data from
    the API response based on discovered record keys.
    """

    def __init__(
        self,
        json_data: Union[dict, Optional[list[dict]]] = None,
        value_delimiter: Optional[str] = "; ",
        ignore_keys: Optional[list] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = True,
    ) -> None:
        """
        Initializes the data processor with JSON data and optional parameters for processing.
        """
        super().__init__()
        self.value_delimiter = value_delimiter
        self.regex = regex
        self.ignore_keys = ignore_keys or None
        self.keep_keys = keep_keys or None

        self.path_node_index = PathNodeIndex()

        self.json_data = json_data
        self.load_data(json_data)

    def load_data(self, json_data: Optional[dict | list[dict]] = None) -> bool:
        """
        Attempts to load a data dictionary or list, contingent of it having
        at least one nonmissing record to load from. If json_data is missing,
        or the json input is equal to the current json_data attribute then
        the json_data attribute will not be updated from the json input.

        Args:
            json_data (Optional[dict | list[dict]]) The json data to be loaded as an attribute
        Returns:
            bool: Indicates whether the data was successfully loaded (True) or not (False)
        """

        if not json_data and not self.json_data:
            logger.debug("JSON is empty")
            return False

        if json_data and json_data != self.json_data:
            logger.debug("Updating JSON data")
            self.json_data = json_data

        discovered_paths = PathDiscoverer(self.json_data).discover_path_elements(
            inplace=False
        )
        self.path_node_index = PathNodeIndex.from_path_mappings(discovered_paths or {})
        # self.path_node_index.index_json(json_data)
        logger.debug("JSON data loaded")
        return True

    def process_record(
        self,
        record_index: int,
        keep_keys: Optional[list] = None,
        ignore_keys: Optional[list] = None,
        regex=None,
    ) -> None:
        """
        Processes a record dictionary to extract record data and article content, creating a processed
        record dictionary with an abstract field. Determines whether or not to retain a specific record
        at the index.
        """
        record_idx_prefix = ProcessingPath(str(record_index))
        indexed_nodes = self.path_node_index.index.filter(record_idx_prefix)

        if not indexed_nodes:
            logger.warning(
                f"A record is not associated with the following index: {record_index}"
            )
            return None

        if any(
            [
                (
                    keep_keys
                    and not self.record_filter(indexed_nodes, keep_keys, regex=regex)
                ),
                self.record_filter(indexed_nodes, ignore_keys, regex=regex),
            ]
        ):
            for path in indexed_nodes:
                self.path_node_index.index.remove(path)
        return None

    def process_page(
        self,
        parsed_records: Optional[list[dict]] = None,
        keep_keys: Optional[list[str]] = None,
        ignore_keys: Optional[list[str]] = None,
        combine_keys: bool = True,
        regex: Optional[bool] = None,
    ) -> list[dict]:
        """
        Processes each individual record dict from the JSON data.
        """

        if parsed_records is not None:
            logger.debug("Processing next page..")
            self.load_data(parsed_records)
        elif self.json_data:
            logger.debug("Processing existing page..")
        else:
            raise ValueError("JSON Data has not been loaded successfully")

        if self.path_node_index is None:
            raise ValueError(
                "JSON data could not be loaded into the processing path index successfully"
            )

        keep_keys = keep_keys or self.keep_keys
        ignore_keys = ignore_keys or self.ignore_keys

        for path in self.path_node_index.index.values():
            self.process_record(
                path.record_index,
                keep_keys=keep_keys,
                ignore_keys=ignore_keys,
                regex=regex,
            )

        if combine_keys:
            self.path_node_index.combine_keys()
        # Process each record in the JSON data
        processed_data = self.path_node_index.simplify_to_rows(
            object_delimiter=self.value_delimiter
        )

        return processed_data

    def record_filter(
        self,
        record_dict: dict[ProcessingPath, Any],
        record_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> bool:
        """
        Indicates whether a record contains a path (key) indicating whether the record as a whole should be retained or droppd.
        """

        if not record_keys:
            return False

        regex = regex if regex is not None else self.regex
        use_regex = regex if regex is not None else False

        record_pattern = "|".join(
            record_keys if use_regex else map(re.escape, as_list_1d(record_keys))
        )

        contains_record_pattern = (
            any(re.search(record_pattern, path.to_string()) for path in record_dict)
            if record_pattern
            else None
        )
        return bool(contains_record_pattern)

    def discover_keys(self) -> Optional[dict]:
        """
        Discovers all keys within the JSON data.
        """
        return self.path_node_index.index.data


if __name__ == "__main__":
    record_test_json: list[dict] = [
        {
            "authors": {"principle_investigator": "Dr. Smith", "assistant": "Jane Doe"},
            "doi": "10.1234/example.doi",
            "title": "Sample Study",
            # "abstract": ["This is a sample abstract.", "keywords: 'sample', 'abstract'"],
            "genre": {"subspecialty": "Neuroscience"},
            "journal": {"topic": "Sleep Research"},
        },
        {
            "authors": {"principle_investigator": "Dr. Lee", "assistant": "John Roe"},
            "doi": "10.5678/example2.doi",
            "title": "Another Study",
            "abstract": "Another abstract.",
            "genre": {"subspecialty": "Psychiatry"},
            "journal": {"topic": "Dreams"},
        },
    ]
    processor = PathDataProcessor(
        value_delimiter="<>", ignore_keys=["abs.*ct"], regex=False
    )
    processed = processor.process_page(record_test_json)

    assert processed
