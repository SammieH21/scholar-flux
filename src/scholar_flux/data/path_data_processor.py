# /data/path_data_processor.py
"""The scholar_flux.data.recursive_data_processor implements the PathDataProcessor that uses a custom path processing
implementation to dynamically flatten and format JSON records to retrieve nested-key value pairs.

Similar to the RecursiveDataProcessor, the PathDataProcessor can be used to dynamically filter, process, and flatten
nested paths while formatting the output based on its specification.

"""

from typing import Any, Optional, Union
from scholar_flux.utils import PathNodeIndex, ProcessingPath, PathDiscoverer, as_list_1d, generate_repr
from scholar_flux.data.abc_processor import ABCDataProcessor
from scholar_flux.exceptions import DataProcessingException, DataValidationException
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
        json_data: Union[dict, Optional[list[dict]]] = None,
        value_delimiter: Optional[str] = "; ",
        ignore_keys: Optional[list] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = True,
        use_cache: Optional[bool] = True,
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

        self.json_data = json_data
        self.lock = threading.Lock()
        self.load_data(json_data)

    @property
    def cached(self) -> bool:
        """Property indicating whether the underlying path node index uses a cache of weakreferences to nodes."""
        return self.path_node_index.node_map.use_cache

    def load_data(self, json_data: Optional[dict | list[dict]] = None) -> bool:
        """Attempts to load a data dictionary or list, contingent on it having at least one non-missing record to load
        from. If `json_data` is missing or the json input is equal to the current `json_data` attribute, then the
        `json_data` attribute will not be updated from the json input.

        Args:
            json_data (Optional[dict | list[dict]]): The json data to be loaded as an attribute
        Returns:
            bool: Indicates whether the data was successfully loaded (True) or not (False)

        """

        if not json_data and not self.json_data:
            return False

        try:
            if json_data and json_data != self.json_data:
                logger.debug("Updating JSON data")
                self.json_data = json_data

            logger.debug("Discovering paths")
            discovered_paths = PathDiscoverer(self.json_data).discover_path_elements(inplace=False)
            logger.debug("Creating a node index")

            self.path_node_index = PathNodeIndex.from_path_mappings(
                discovered_paths or {}, chain_map=True, use_cache=self.use_cache
            )
            logger.debug("JSON data loaded")
            return True
        except DataValidationException as e:
            raise DataValidationException(
                f"The JSON data of type {type(self.json_data)} could not be successfully "
                f"processed and loaded into an index: {e}"
            )

    def process_record(
        self,
        record_index: int,
        keep_keys: Optional[list] = None,
        ignore_keys: Optional[list] = None,
        regex=None,
    ) -> None:
        """Processes a record dictionary to extract record data and article content, creating a processed record
        dictionary with an abstract field.

        Determines whether or not to retain a specific record at the index.

        """
        logger.debug("Processing next record...")

        record_idx_prefix = ProcessingPath(str(record_index))
        indexed_nodes = self.path_node_index.node_map.filter(record_idx_prefix)

        if not indexed_nodes:
            logger.warning(f"A record is not associated with the following index: {record_index}")
            return None

        if any(
            [
                (keep_keys and not self.record_filter(indexed_nodes, keep_keys, regex=regex)),
                self.record_filter(indexed_nodes, ignore_keys, regex=regex),
            ]
        ):
            for path in indexed_nodes:
                self.path_node_index.node_map.remove(path)
        return None

    def process_page(
        self,
        parsed_records: Optional[list[dict]] = None,
        keep_keys: Optional[list[str]] = None,
        ignore_keys: Optional[list[str]] = None,
        combine_keys: bool = True,
        regex: Optional[bool] = None,
    ) -> list[dict]:
        """Processes each individual record dict from the JSON data."""
        self._validate_inputs(ignore_keys, keep_keys, regex, value_delimiter=self.value_delimiter)

        try:
            if parsed_records is not None:
                logger.debug("Processing next page..")
                self.load_data(parsed_records)
            elif self.json_data:
                logger.debug("Processing existing page..")
            else:
                raise ValueError("JSON Data has not been loaded successfully")

            if self.path_node_index is None:
                raise ValueError("JSON data could not be loaded into the processing path index successfully")

            keep_keys = keep_keys or self.keep_keys
            ignore_keys = ignore_keys or self.ignore_keys

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
        except DataProcessingException as e:
            raise DataProcessingException(f"An error occurred during data processing: {e}")

    def record_filter(
        self,
        record_dict: dict[ProcessingPath, Any],
        record_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
    ) -> bool:
        """Indicates whether a record contains a path (key) indicating whether the record as a whole should be retained
        or dropped."""

        if not record_keys:
            return False

        regex = regex if regex is not None else self.regex
        use_regex = regex if regex is not None else False

        record_pattern = "|".join(record_keys if use_regex else map(re.escape, as_list_1d(record_keys)))

        contains_record_pattern = (
            any(re.search(record_pattern, path.to_string()) for path in record_dict) if record_pattern else None
        )
        return bool(contains_record_pattern)

    def discover_keys(self) -> Optional[dict[str, Any]]:
        """Discovers all keys within the JSON data."""
        return {str(node.path): node for node in self.path_node_index.nodes}

    def structure(self, flatten: bool = False, show_value_attributes: bool = False) -> str:
        """Method for showing the structure of the current PathDataProcessor and identifying the current configuration.

        Useful for showing the options being used to process the api response records

        """
        return generate_repr(
            self, flatten=flatten, show_value_attributes=show_value_attributes, exclude={"json_data", "use_cache"}
        )

    def __call__(self, *args, **kwargs) -> list[dict]:
        """Convenience method that calls process_page while also locking the class for processing while a single page is
        processed.

        Useful in a threading context where multiple SearchCoordinators may be using the same PathDataProcessor.

        """
        with self.lock:
            return self.process_page(*args, **kwargs)


__all__ = ["PathDataProcessor"]
