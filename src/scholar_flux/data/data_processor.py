from typing import Any, Dict, List, Optional
from implicitrie.utils import FileUtils
from ..utils import get_nested_data, as_list_1d, nested_key_exists
import re

import logging
logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Initializes record keys and header/body paths in the object instance using defined methods.

    Processes a specific key from record by joining non-None values into a string.

    Processes a record dictionary to extract record and article content, creating a processed record dictionary with an abstract field.

    Processes a list of raw page record dict data from the API response based on record keys.

    Returns:
    - None
    """
    def __init__(self, record_keys: Optional[Dict[Any,Any]]=None, header_path: Optional[List]=None, body_path: Optional[List] = None, ignore_records_with: Optional[List] = None,regex: Optional[bool]=True) -> None:
        """
        Initializes record keys and header/body paths in the object instance using defined methods.

        Returns:
        - None
        """
        self.record_keys = self.define_record_keys(record_keys)
        self.header_path, self.body_path = self.define_record_path(header_path, body_path)
        self.ignore_keys =  self.ignore_record_keys(ignore_records_with)
        self.auto_search_keys=['title','author','creator','article','abstract']
        self.regex=regex


    def define_record_keys(self, keys=None):
        default_keys={
            'identifier': 'dc:identifier',
            'language': 'dc:language',
            'title': 'dc:title',
            'pubdate': 'prism:publicationDate',
            'authors': 'dc:creator',
            'publicationName': 'prism:publicationName',
            'issn': 'prism:issn',
            'eIssn': 'prism:eIssn',
            'doi': 'prism:doi',
            'volume': 'prism:volume',
            'issueNumber': 'prism:number',
            'startingPage': 'prism:startingPage',
            'endingPage': 'prism:endingPage',
            'urlList': 'prism:url',
            'genre': 'prism:genre',
            'copyright': 'prism:copyright',
            'keywords': 'prism:keyword',
        }
        return keys or default_keys

    def ignore_record_keys(self,keys=None):
        default_keys = keys or ['.*facets.*','.*facet-value.*']
        return default_keys


    def define_record_path(self, header=None, body=None):
        """
        Defines header and body paths for record extraction, with default paths provided if not specified
        """
        default_header=['pam:message', 'pam:article', 'xhtml:head']
        default_body=['pam:message', 'pam:article', 'xhtml:body','xhtml:p']

        return header or default_header, body or default_body
    
    def discover_key(self,record: Dict,key: str):
        
        
        record_keys = record.keys()
        
        for key, data in record.items():
            if isinstance(record,list):
                return discover_key
        
        
        

    def process_key(self,record,key):
        """
        Processes a specific key from record by joining non-None values into a string.

        Args:
        - record: The record dictionary to extract the key from.
        - key: The key to process within the record dictionary.

        Returns:
        - str: A string containing non-None values from the specified key in the record dictionary, joined by '; '.
        """
        if not record:
            return None
        record_field = as_list_1d(record.get(key, []))
        if record_field:
            return "; ".join(str(v) for v in record_field if v is not None)

    def process_text(self, record_dict):
        """
        Processes a record dictionary to extract record and article content, creating a processed record dictionary with an abstract field.

        Args:
        - record_dict: The dictionary containing the record data.

        Returns:
        - str: A processed text/abstract created from the article content.
        """
        
        # Convert current_article to a 1D list and join non-None paragraphs
        current_article = get_nested_data(record_dict, self.body_path)
        abstract = "\n".join(p for p in as_list_1d(current_article) if p is not None) if current_article else None
        return abstract
    
    def process_record(self, record_dict):
        """
        Processes a record dictionary to extract record data and article content, creating a processed record dictionary with an abstract field.

        Args:
        - record_dict: The dictionary containing the record data.

        Returns:
        - dict: A processed record dictionary with record keys processed and an abstract field created from the article content.
        """


        
        # retrieve a dict containing the fields for the current record
        record_data = get_nested_data(record_dict, self.header_path)

        # Simplified record data processing using dictionary comprehension
        processed_record_dict = {
            col: self.process_key(record_data, key) for col, key in self.record_keys.items()
        }

        processed_record_dict['abstract']= self.process_text(record_dict)
        return processed_record_dict

    def process_page(self, parsed_records,ignore_keys:Optional[List[str]]=None,regex: Optional[bool]=None):

        
        
        # processes each individual record dict
        processed_record_dict_list=[self.process_record(record_dict) for record_dict in parsed_records
                                    if not self.record_filter(record_dict, ignore_keys or self.ignore_keys, regex or self.regex)]

        logging.info(f"total included records - {len(processed_record_dict_list)}")
                                   

        # return the list of processed record dicts
        return processed_record_dict_list
    
    def record_filter(self,record_dict:Dict,record_keys: Optional[List[str]]=None,regex:Optional[bool]=None) -> bool:
        ''' filter records, using regex pattern matching, checking if any of the keys provided in the function call exist '''
        use_regex = regex if regex is not None else False
        if record_keys:
            logger.debug(f"Finding field key matches within processing data: {record_keys}")
            matches=[nested_key_exists(record_dict,key,regex=use_regex) for key in record_keys] or []
            return len([match for match in matches if match]) > 0 
        return False

if __name__ == '__main__':
    sample_json=FileUtils.load_data("~/Downloads/sleep.json")
    if not isinstance(sample_json,str):
        processor = DataProcessor()
        processed = processor.process_page(sample_json)
