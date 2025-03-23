from ..api import ResponseValidator,DataCacheManager
from ..data import DataExtractor, DataParser, DataProcessor 
from ..exceptions.data_exceptions import DataParsingException, InvalidDataFormatException, RequiredFieldMissingException, DataExtractionException, FieldNotFoundException, DataProcessingException, DataValidationException
from typing import Optional, Dict, List, Any

import logging
logger = logging.getLogger(__name__)



class ResponseCoordinator:
    def __init__(self, parser, data_extractor, processor,cache_manager: Optional[DataCacheManager] = None):
        self.parser = parser
        self.data_extractor = data_extractor
        self.processor = processor
        self.cache_manager = cache_manager

        ####
        #self.api_key = api_key
        #self.response_type = 
        #self.status_code = None
        
        #self.total_records = None
        #self.page_length = None
        #self.total_displayed_records = None
        
        #self.response_data_dictionary = OrderedDict()
        #self.data_parser = DataParser()
        #self.data_processor = DataProcessor()

    def handle_response(self, response,cache_key=None):
        # if caching is not being being used, or the cache is not available or valid anymore, process:
        if self.cache_manager is not None:
            cache_key=cache_key or self.cache_manager.generate_fallback_cache_key(response)
            if self.cache_manager.cache_is_valid(cache_key, response):
                logger.info(f"retrieving response: {cache_key}")
                response_processing_cache =  self.cache_manager.retrieve(cache_key)
                return response_processing_cache.get('processed_response') if response_processing_cache else []
        
        logger.info(f"processing response: {cache_key}")
        return self.parse_and_process_response(response, cache_key)
        


    def parse_and_process_response(self, response, cache_key):
        try:
            parsed_data = self.parser.parse(response)
            parsed_record_data, query_metadata_info = self.data_extractor.extract(parsed_data) if self.data_extractor else {}
            processed_response = self.processor.process_page(parsed_record_data) if parsed_record_data else None    
            if cache_key and self.cache_manager:
                logger.debug("adding_to_cache")
                self.cache_manager.update_cache(cache_key,response,
                                        store_raw=True,
                                        metadata=query_metadata_info,
                                        parsed_response=parsed_data,
                                        extracted_records=parsed_record_data,
                                        processed_response=processed_response)
            logger.info("Data processed for %s",cache_key)
            return processed_response
            
        except (DataParsingException, DataExtractionException, DataProcessingException,FieldNotFoundException) as e:
            logger.error(f"Error processing response: {e}")
            return None
            
    
    
