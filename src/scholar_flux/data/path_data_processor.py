from typing import Dict, List, Any, Optional, DefaultDict, Union
from scholar_flux.utils import (PathNodeIndex, PathNode, PathSimplifier,
                                ProcessingPath, PathDiscoverer)
from scholar_flux.data.base_processor import BaseDataProcessor
# from scholar_flux.data.recursive_data_processor import RecursiveDataProcessor
# from scholar_flux.data.dynamic_data_processor import DynamicDataProcessor
from scholar_flux.utils import FileUtils
import re
import logging


logger = logging.getLogger(__name__)

class PathDataProcessor(BaseDataProcessor):
    """
    Processes a list of raw page record dict data from the API response based on discovered record keys.
    """

    def __init__(self, json_data: Union[dict,Optional[list[dict]]]=None,
                 delimiter: Optional[str] = None,
                 value_delimiter: str = "; ",
                 ignore_keys: Optional[list] = None,
                 keep_keys: Optional[list[str]] = None,
                 regex: Optional[bool] = True) -> None:
        """
        Initializes the data processor with JSON data and optional parameters for processing.
        """
        super().__init__()
        self.delimiter=delimiter
        self.value_delimiter=value_delimiter
        self.regex = regex
        self.ignore_keys = ignore_keys or None
        self.keep_keys = keep_keys or None
        self.json_data = json_data
        self.key_discoverer = None

        self.path_node_index = PathNodeIndex()
        self.load_data(json_data)

    def load_data(self,json_data: Optional[dict | list[dict]] = None)->bool:
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

        discovered_paths = PathDiscoverer(self.json_data).discover_path_elements(inplace=False)
        self.path_node_index = PathNodeIndex.from_path_mappings(discovered_paths or {})
        #self.path_node_index.index_json(json_data)
        logger.debug("JSON data loaded")
        return True


    def process_page(self,
                     parsed_records: Optional[list[dict]]=None,
                     keep_keys: Optional[list[str]]=None,
                     ignore_keys: Optional[list[str]] = None,
                     combine_keys: bool = True,
                     regex: Optional[bool] = None) -> Union[list[dict[str, Any]], list[DefaultDict[str, Any]]]:
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
            raise ValueError("Index was not loaded")


        keep_keys = keep_keys or self.keep_keys
        keep_pattern = '|'.join(keep_keys) if keep_keys else None
        ignore_keys = ignore_keys or self.ignore_keys
        ignore_pattern = '|'.join(ignore_keys) if ignore_keys else None
        regex = regex if regex is not None else self.regex

        indices=set(str(path.record_index) for path in self.path_node_index.index.values())

        for idx in indices:
            idx_key = ProcessingPath(idx)
            indexed_nodes = self.path_node_index.index.filter(idx_key)

            contains_keep_pattern = any(re.search(keep_pattern, path.to_string()) for path in indexed_nodes) if keep_pattern else None
            contains_ignore_pattern = any(re.search(ignore_pattern, path.to_string()) for path in indexed_nodes) if ignore_pattern else None
            if any([contains_keep_pattern is not None and not contains_keep_pattern,
                    contains_ignore_pattern is not None and contains_ignore_pattern]):
                for path in indexed_nodes:
                    self.path_node_index.index.remove(path)


        if combine_keys:
            self.path_node_index.combine_keys()
        # Process each record in the JSON data
        processed_data = self.path_node_index.simplify_to_rows(object_delimiter=self.value_delimiter)


        return processed_data

#   def ignore_record_keys(self, keys=None):
#       default_keys = keys or ['.*facets.*', '.*facet-value.*']
#       return default_keys

#   def keep_record_keys(self, keys=None):
#       #        default_keys = keys or ['.*abstract.*']
#       #        return default_keys
#       return keys

#   def process_text(self, record_dict: dict[str, Any], body_path: list[str]) -> Optional[str]:
#       """
#       Processes a record dictionary to extract article content, creating a processed text/abstract.
#       """
#       current_article = self.get_nested_data(record_dict, body_path)
#       if isinstance(current_article, list):
#           return "\n".join(p for p in current_article if p is not None)
#       return current_article if current_article else None

#   def process_record(self, record_dict: dict[str, Any], header_path: list[str], body_path: list[str]) -> dict[str, Any]:
#       """
#       Processes a record dictionary to extract record data and article content, creating a processed record dictionary with an abstract field.
#       """
#       # Retrieve a dict containing the fields for the current record
#       record_data = self.get_nested_data(record_dict, header_path)

#       # Discover and process record keys dynamically
#       discovered_keys = self.discover_keys()
#       processed_record_dict = {
#           col: self.process_key(record_data, key) for col, paths in discovered_keys.items() for key in paths
#       }

#       # Extract abstract text from the body path
#       processed_record_dict['abstract'] = self.process_text(record_dict, body_path)
#       return processed_record_dict

# Example usage:
if __name__ == '__main__':
    sample_json=FileUtils.load_data("~/Downloads/sleep.json")
    if not isinstance(sample_json,str):
        # if not is instance
        print('testing')
        from scholar_flux import initialize_package
        initialize_package(logging_params=dict(log_level=logging.WARNING))
        # %timeit processed = PathDataProcessor(sample_json,delimiter='.').process_page(keep_keys=['abstract'],combine_keys=True)
        # %timeit processed = DynamicDataProcessor(sample_json,delimiter='.').process_page(keep_keys=['abstract'])
        # %timeit processed = RecursiveDataProcessor(sample_json,delimiter='<>',keep_keys=['abstract']).process_page()
        processor = PathDataProcessor(sample_json,delimiter='<>',keep_keys=['abstract'])
        processed2 = processor.process_page()




        ##cache_nodes99={node for nodes in processor.trie.index._cache._cache.values() for node in nodes if node.has_ancestor('99')}
        ##nodes99=[node for node in processor.trie.index.values() if node.full_path.has_ancestor('99')]

        ##{k for k in cache_nodes99 if k not in (node.full_path for node in nodes99)}
        ##{node.full_path for node in nodes99 if node.full_path not in cache_nodes99}

        ##processor.trie.index.pop(nodes99[0].full_path)
        ##[processor.trie.index.pop(node.full_path,None) for node in nodes99]
        ##{processor.trie.index.pop(path.full_path,None) for path in nodes99}

        ##{k for k in list(processor.trie.index._cache.filter(ProcessingNode('99'))) if k not in processor.trie.index.keys()}
        ##{k for k in nodes99 if k.full_path not in list(processor.trie.index._cache.filter(ProcessingNode('99')))}
        ##cached_nodes = {value for values in processor.trie.index._cache._cache.values() for value in values}

        ###processor.json_data[30]
        ###processed[30]
        ##discovered_keys = processor.discover_keys()
        ##filtered_keys_by_prefix = processor.filter_keys(prefix='address')
        ##filtered_keys_by_length = processor.filter_keys(min_length=3)
        ##filtered_keys_by_substring = processor.filter_keys(substring='state')

        ##print("Discovered Keys:", discovered_keys)
        ##print("Filtered Keys by Prefix:", filtered_keys_by_prefix)

        ##print("Filtered Keys by Length:", filtered_keys_by_length)
        ##print("Filtered Keys by Substring:", filtered_keys_by_substring)
        ##print("Processed Records:", processed_records)

