# /data/path_data_processor.py
"""The scholar_flux.data.path_data_processor implements the PathDataProcessor that uses a custom path processing
implementation to dynamically flatten and format JSON records to retrieve nested-key value pairs.

Similar to the RecursiveDataProcessor, the PathDataProcessor can be used to dynamically filter, process, and flatten
nested paths while formatting the output based on its specification.

"""

from typing import Any
from scholar_flux.utils import PathNodeIndex, ProcessingPath, PathDiscoverer, as_list_1d, generate_repr
from scholar_flux.data.abc_processor import ABCDataProcessor
from scholar_flux.exceptions import DataProcessingException, DataValidationException
from scholar_flux.utils.record_types import RecordType, RecordList
import threading

import re
import logging


logger = logging.getLogger(__name__)


class PathDataProcessor(ABCDataProcessor):
    """The PathDataProcessor uses a custom implementation of Trie-based processing to abstract nested key-value
    combinations into path-node pairs where the path defines the full range of nested keys that need to be traversed to
    arrive at each terminal field within each individual record.

    This implementation automatically and dynamically flattens and filters a single page of records (a list
    of dictionary-based records) extracted from a response at a time to return the processed record data.

    Example:
        >>> from scholar_flux.data import PathDataProcessor
        >>> path_data_processor = PathDataProcessor() # instantiating the class
        >>> data = [{'id':1, 'a':{'b':'c'}}, {'id':2, 'b':{'f':'e'}}, {'id':2, 'c':{'h':'g'}}]
        ### The process_page method can then be referenced using the processor as a callable:
        >>> result = path_data_processor(data) # recursively flattens and processes by default
        >>> print(result)
        # OUTPUT: [{'id': '1', 'a.b': 'c'}, {'id': '2', 'b.f': 'e'}, {'id': '2', 'c.h': 'g'}]

    """

    def __init__(
        self,
        json_data: RecordType | RecordList | None = None,
        value_delimiter: str | None = None,
        ignore_keys: list | None = None,
        keep_keys: list[str] | None = None,
        regex: bool | None = True,
        use_cache: bool | None = True,
    ) -> None:
        """Initializes the data processor with JSON data and optional parameters for processing."""
        super().__init__()
        self._validate_inputs(ignore_keys, keep_keys, regex, value_delimiter=value_delimiter)
        self.value_delimiter = value_delimiter
        self.regex = regex
        self.ignore_keys = ignore_keys or None
        self.keep_keys = keep_keys or None
        self.use_cache = use_cache or False
        self.path_node_index = PathNodeIndex(use_cache=self.use_cache)

        self.json_data = None
        self.lock = threading.Lock()
        self.load_data(json_data)

    @property
    def cached(self) -> bool:
        """Property indicating whether the underlying path node index uses a cache of weakreferences to nodes."""
        return self.path_node_index.node_map.use_cache

    @property
    def json_data(self) -> RecordList | None:
        """A list of dictionary-based records to further process."""
        return self._json_data

    @json_data.setter
    def json_data(self, data: RecordType | RecordList | None) -> None:
        """A list of dictionary-based records to further process."""
        if isinstance(data, dict):
            data = [data]

        self._validate_json_data(data)
        self._json_data = data

    def load_data(self, json_data: RecordType | RecordList | None = None) -> bool:
        """Attempts to load a data dictionary or list, contingent on the input having at least one non-missing record.

        If `json_data` is missing or the json input is equal to the current `json_data` attribute, then the
        `json_data` attribute will not be updated from the json input.

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

            logger.debug("Discovering paths...")
            discovered_paths = PathDiscoverer(self.json_data).discover_path_elements(inplace=False)
            logger.debug("Creating a node index...")

            self.path_node_index = (
                PathNodeIndex.from_path_mappings(discovered_paths or {}, chain_map=True, use_cache=self.use_cache)
                if self.json_data
                else PathNodeIndex()
            )
            logger.debug("JSON data loaded.")
            return True
        except DataValidationException as e:
            raise DataValidationException(
                f"The JSON data could not be successfully loaded and processed into an index: {e}"
            )

    def process_record(
        self,
        record_index: int,
        keep_keys: list | None = None,
        ignore_keys: list | None = None,
        regex: bool | None = None,
    ) -> None:
        """Processes the current record dictionary, indicating if the record at the index should be retained or dropped.

        The full set of processed records is subsequently accessible via
        `processor.path_node_index.simplify_to_rows()`.

        """
        logger.debug("Processing next record...")

        record_idx_prefix = ProcessingPath(str(record_index))
        indexed_nodes = self.path_node_index.node_map.filter(record_idx_prefix)

        if not indexed_nodes:
            logger.warning(f"A record is not associated with the following index: {record_index}")
            return

        if any(
            [
                (keep_keys and not self.record_filter(indexed_nodes, keep_keys, regex=regex)),
                self.record_filter(indexed_nodes, ignore_keys, regex=regex),
            ]
        ):
            for path in indexed_nodes:
                self.path_node_index.node_map.remove(path)
        return

    def process_page(
        self,
        parsed_records: RecordType | RecordList | None = None,
        keep_keys: list[str] | None = None,
        ignore_keys: list[str] | None = None,
        combine_keys: bool = True,
        regex: bool | None = None,
    ) -> RecordList:
        """Processes each individual record dict from the JSON data."""
        self._validate_inputs(ignore_keys, keep_keys, regex, value_delimiter=self.value_delimiter)

        try:
            if parsed_records is not None:
                logger.debug("Processing next page..")
                self.load_data(parsed_records)
            elif self.json_data:
                logger.debug("Processing existing page..")

            if self.json_data is None:
                raise DataValidationException(
                    "JSON data could not be successfully loaded into the JSON processing index."
                )

            keep_keys = keep_keys or self.keep_keys
            ignore_keys = ignore_keys or self.ignore_keys
            regex = regex if regex is not None else self.regex

            for record_index in self.path_node_index.record_indices:
                self.process_record(
                    record_index,
                    keep_keys=keep_keys,
                    ignore_keys=ignore_keys,
                    regex=regex,
                )

            if combine_keys:
                self.path_node_index.combine_keys()
            # Process each record in the JSON data
            processed_data = self.path_node_index.simplify_to_rows(object_delimiter=self.value_delimiter)

            return processed_data
        except DataProcessingException:
            raise
        except Exception as e:
            raise DataProcessingException(f"An unexpected error occurred during data processing: {e}")

    @classmethod
    def record_filter(
        cls,
        record_dict: dict[ProcessingPath, Any],
        record_keys: list[str] | None = None,
        regex: bool | None = None,
    ) -> bool:
        """Identifies whether a record contains a path (key), indicating whether the record should be retained."""
        if not record_keys:
            return False

        use_regex = regex if regex is not None else False

        record_pattern = "|".join(record_keys if use_regex else map(re.escape, as_list_1d(record_keys)))

        contains_record_pattern = (
            any(re.search(record_pattern, path.to_string()) for path in record_dict) if record_pattern else None
        )
        return bool(contains_record_pattern)

    def discover_keys(self) -> dict[str, Any] | None:
        """Discovers all keys within the JSON data."""
        return {str(node.path): node for node in self.path_node_index.nodes}

    def structure(self, flatten: bool = False, show_value_attributes: bool = False) -> str:
        """Method for showing the structure of the current PathDataProcessor and identifying the current configuration.

        Useful for showing the options being used to process the API response records.

        """
        return generate_repr(
            self, flatten=flatten, show_value_attributes=show_value_attributes, exclude={"_json_data", "use_cache"}
        )

    def __call__(self, *args: Any, **kwargs: Any) -> list[dict]:
        """Convenience method that applies a thread lock and processes a single page of JSON data via `.process_page()`.

        Useful in a threading context where multiple SearchCoordinators may be using the same PathDataProcessor.

        """
        with self.lock:
            return self.process_page(*args, **kwargs)


__all__ = ["PathDataProcessor"]
