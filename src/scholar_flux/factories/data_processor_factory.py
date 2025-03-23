from typing import Dict, List, Optional, Union, Tuple, Callable
from ..data.data_processor import DataProcessor
import logging
logger = logging.getLogger(__name__)

class DataProcessorFactory:
    def __init__(self):
        # This dictionary maps processor names to their specific factory methods
        self.processors = {
            "pam": self.create_pam_processor,
            "json": self.create_json_processor,
            # Add more mappings as necessary
        }

    def get_processor(self, name: str) -> Optional[DataProcessor]:
        """ Retrieves a DataProcessor based on a given name. """
        factory_method = self.processors.get(name)
        if not factory_method:
            logger.error(f"No processor found for {name}")
            return None
        return factory_method()

    @staticmethod
    def create_pam_processor() -> DataProcessor:
        """ Factory method for creating a DataProcessor configured for PAM responses. """
        record_keys={
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
        
        header=['pam:message', 'pam:article', 'xhtml:head']
        body=['pam:message', 'pam:article', 'xhtml:body','xhtml:p']
        
        
        #record_path = ['response', 'records', 'record']
        return DataProcessor(record_keys=record_keys, header_path=header,body_path=body,ignore_records_with=['facet-value'],regex=False)
    
    @staticmethod
    def create_json_processor() -> DataProcessor:
        """ Factory method for creating a DataProcessor configured for JSON responses. """
        ...
        
        record_keys = {
            'contentType': 'contentType',
            'identifier': 'identifier',
            'language': 'language',
            'urls': 'url',  # Process this list of URLs accordingly
            'title': 'title',
            'creators': 'creators',  # Assume handling list of creators
            'publicationName': 'publicationName',
            'openAccess': 'openaccess',
            'doi': 'doi',
            'publisher': 'publisher',
            'publisherName': 'publisherName',
            'publicationDate': 'publicationDate',
            'issn': 'issn',
            'eIssn': 'eIssn',
            'volume': 'volume',
            'issueNumber': 'number',
            'startingPage': 'startingPage',
            'endingPage': 'endingPage',
            'keywords': 'keyword',  # Assume handling list of keywords
            'abstract': 'abstract',
        }
        
        header=[]
        body=[]
        return DataProcessor(record_keys=record_keys, header_path=header,body_path=body)

# Usage
factory = DataProcessorFactory()
factory.create_json_processor()
