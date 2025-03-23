from typing import Dict, List, Any, Optional, DefaultDict, Union
from implicitrie.tries import SparseTrie, TriePath
from implicitrie.utils import FileUtils
import re
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sparselogger = logging.getLogger('SparseTrieLogger')
sparselogger.setLevel(logging.INFO)


logger = logging.getLogger('new')

class DynamicDataProcessor:
    """
    Processes a list of raw page record dict data from the API response based on discovered record keys.
    """

    def __init__(self, json_data: Union[Dict,Optional[List[Dict]]]=None, delimiter: Optional[str] = '<>', obj_delimiter: str = "; ", ignore_records_paths: Optional[List] = None,
                 keep_records_paths: Optional[List[str]] = None, regex: Optional[bool] = True) -> None:
        """
        Initializes the data processor with JSON data and optional parameters for processing.
        """
        self.delimiter=delimiter
        self.obj_delimiter=obj_delimiter
        self.ignore_records_paths=ignore_records_paths
        self.keep_records_paths=keep_records_paths
        self.regex = regex
        self.ignore_keys = self.ignore_record_keys(self.ignore_records_paths)
        self.keep_keys = self.keep_record_keys(self.keep_records_paths)
        self.json_data = None
        self.key_discoverer = None
        self.trie = SparseTrie(delimiter=self.delimiter)
        self.load_data(json_data)
        
    def load_data(self,json_data: Union[Dict,Optional[List[Dict]]]=None):
        if json_data:
            self.json_data = json_data
            self.trie.index_json(self.json_data)
            logger.debug("JSON data loaded")


    def ignore_record_keys(self, keys=None):
        default_keys = keys or ['.*facets.*', '.*facet-value.*']
        return default_keys

    def keep_record_keys(self, keys=None):
        #        default_keys = keys or ['.*abstract.*']
        #        return default_keys
        return keys

#   def process_text(self, record_dict: Dict[str, Any], body_path: List[str]) -> Optional[str]:
#       """
#       Processes a record dictionary to extract article content, creating a processed text/abstract.
#       """
#       current_article = self.get_nested_data(record_dict, body_path)
#       if isinstance(current_article, list):
#           return "\n".join(p for p in current_article if p is not None)
#       return current_article if current_article else None

#   def process_record(self, record_dict: Dict[str, Any], header_path: List[str], body_path: List[str]) -> Dict[str, Any]:
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

    def process_page(self, json_data: Optional[List[Dict]]=None, keep_keys: Optional[List[str]]=None,ignore_keys: Optional[List[str]] = None, regex: Optional[bool] = None) -> Union[List[Dict[str, Any]],List[DefaultDict[str, Any]]]:
        """
        Processes each individual record dict from the JSON data.
        """
        
        if json_data is not None:
            logger.debug("Processing next page..")
            self.load_data(json_data) 
        elif self.json_data:
            logger.debug("Reprocessing existing page..")
        else:
            raise ValueError("JSON Data has not been loaded successfully")


        keep_keys = keep_keys or self.keep_keys
        keep_pattern = '|'.join(keep_keys) if keep_keys else None
        ignore_keys = ignore_keys or self.ignore_keys
        ignore_pattern = '|'.join(ignore_keys) if ignore_keys else None
        regex = regex if regex is not None else self.regex

        if keep_pattern:
            self.trie.filter(keep_pattern, keep=True)

        if ignore_pattern:
            self.trie.filter(ignore_pattern)

        processed_data = self.trie.combine_keys()
        # Process each record in the JSON data
        processed_data = self.trie.collapse_indexed_trie()

        
        return processed_data

# Example usage:
if __name__ == '__main__':
    sample_json=FileUtils.load_data("~/Downloads/sleep.json")
    if not isinstance(sample_json,str):
        # if not is instance
        processor = DynamicDataProcessor(sample_json,delimiter='%')
        #{processor.trie.remove(node) for node in processor.trie.search_fullmatch('99.*') if node is not None}
        #processor.trie.combine_keys()
        #processor.collapse_indexed_trie()
        processed = processor.process_page()


        nodes99=list(processor.trie.implicit_search('99').terminal_nodes.values())
        node1 = nodes99[0]
        pth=node1.full_path
        new_pth = pth / 'Anotherpath'
        new_node=node1.update(full_path=new_pth)
        processor.trie.update_with_node(pth,new_node)
        processor.trie.implicit_search(pth)
        processor.trie.search(new_node.full_path,search_exact=True)
        cache_nodes99={node for nodes in processor.trie.terminal_nodes._cache._cache.values() for node in nodes if node.has_ancestor('99')}
        nodes99=[node for node in processor.trie.terminal_nodes.values() if node.full_path.has_ancestor('99')]

        {k for k in cache_nodes99 if k not in (node.full_path for node in nodes99)}
        {node.full_path for node in nodes99 if node.full_path not in cache_nodes99}

        processor.trie.terminal_nodes.pop(nodes99[0].full_path)
        [processor.trie.terminal_nodes.pop(node.full_path,None) for node in nodes99]
        {processor.trie.terminal_nodes.pop(path.full_path,None) for path in nodes99}
        #res=processor.trie.search('99',search_exact=False)
        #processor.trie.combine_keys()
        {k for k in list(processor.trie.terminal_nodes._cache.filter(TriePath('99'))) if k not in processor.trie.terminal_nodes.keys()}
        {k for k in nodes99 if k.full_path not in list(processor.trie.terminal_nodes._cache.filter(TriePath('99')))}
        cached_nodes = {value for values in processor.trie.terminal_nodes._cache._cache.values() for value in values}

        processor.trie.terminal_nodes._cache.updates
        #processor.json_data[-3]
        #processed[-3]
        discovered_keys = processor.discover_keys()
        filtered_keys_by_prefix = processor.filter_keys(prefix='address')
        filtered_keys_by_length = processor.filter_keys(min_length=3)
        filtered_keys_by_substring = processor.filter_keys(substring='state')

        #processed_records = processor.process_page()

        print("Discovered Keys:", discovered_keys)
        print("Filtered Keys by Prefix:", filtered_keys_by_prefix)
        print("Filtered Keys by Length:", filtered_keys_by_length)
        print("Filtered Keys by Substring:", filtered_keys_by_substring)
        print("Processed Records:", processed_records)

