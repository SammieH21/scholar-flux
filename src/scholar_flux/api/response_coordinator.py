from scholar_flux.data_storage import DataCacheManager
from scholar_flux.data import DataExtractor, DataParser, BaseDataProcessor
from scholar_flux.exceptions.data_exceptions import (ResponseProcessingException,
                                                     DataParsingException,
                                                     InvalidDataFormatException,
                                                     RequiredFieldMissingException,
                                                     DataExtractionException,
                                                     FieldNotFoundException,
                                                     DataProcessingException,
                                                     DataValidationException)
from scholar_flux.exceptions.storage_exceptions import StorageCacheException
from typing import Optional, Dict, List, Any, Union
from requests import Response

import logging
logger = logging.getLogger(__name__)

from scholar_flux.api.models import ProcessedResponse


class ResponseCoordinator:
    """
    Coordinates the parsing, extraction, processing, and caching of API responses.

    Args:
        parser (DataParser): Parses raw API responses.
        data_extractor (DataExtractor): Extracts records and metadata.
        processor (BaseDataProcessor): Processes extracted data.
        cache_manager (DataCacheManager): Manages response cache.
    """

    def __init__(self, parser:DataParser,
                 data_extractor:DataExtractor,
                 processor:BaseDataProcessor,
                 cache_manager: DataCacheManager):

        self.parser = parser
        self.data_extractor = data_extractor
        self.processor = processor
        self.cache_manager = cache_manager

    def handle_response_data(self, response: Response,cache_key: Optional[str] = None)-> Optional[List[Dict[Any, Any]] | List]:
        """
        Retrieves the data from the processed response from cache if previously cached.
        Otherwise the data is retrieved after processing the response.

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing/retrieving.

        Returns:
            Optional[List[Dict[Any, Any]]]: Processed response data or None.
        """

        # if caching is not being being used, or the cache is not available or valid anymore, process:
        return self.handle_response(response, cache_key).data

    def handle_response(self,
                        response: Response,
                        cache_key: Optional[str] = None,
                        from_cache: bool = True) -> ProcessedResponse:
        """
        Retrieves the data from the processed response from cache as a
          if previously cached. Otherwise the data is retrieved
          after processing the response. The response data is
          subsequently transformed into a dataclass containing
          the response content, processing info, and metadata

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing/retrieving.
            from_cache: (bool): Should we try to retrieve the processed response from the cache?

        Returns:
            ProcessedResponse: A Dataclass Object that contains response data
                               and detailed processing info.
        """

        cached_response = None

        if from_cache:
            # attempt to retrieve from cache first
            cached_response = self._from_cache(response, cache_key)

        # if caching is not being being used, or the cache is not available or valid anymore, process:
        return cached_response or self._process_response(response, cache_key)


    def _from_cache(self, response: Response,cache_key: Optional[str] = None)-> Optional[ProcessedResponse]:
        """
        Retrieves Previously Cached Response data that has been
        parsed, extracted, processed, and stored in cache

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.

        Returns:
            Optional[ProcessedResponse]: Processed response data or None.
        """
        try:
            if not self.cache_manager:
                return None

            cache_key=cache_key or self.cache_manager.generate_fallback_cache_key(response)

            if not self.cache_manager.cache_is_valid(cache_key, response):
                return None

            cached = self.cache_manager.retrieve(cache_key) or {}

            if not cached:
                return None

            logger.info(f"retrieved response '{cache_key}' from cache")

            return ProcessedResponse(
                data=cached.get('processed_response'),
                metadata=cached.get('metadata'),
                cache_key=cache_key,
                response=response,
                parsed_response=cached.get('parsed_response'),
                extracted_records=cached.get('extracted_records')
            )
        except StorageCacheException as e:
            logger.warning(f"An exception occurred while attempting to retrieve '{cache_key}' from cache: {e}")
            return None


    def _process_response(self, response: Response, cache_key: Optional[str] = None)-> ProcessedResponse:
        """
        Parses, extracts, processes, and optionally caches response data.

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.

        Returns:
            ProcessedResponse: A Dataclass Object that contains response data
                               and detailed processing info.
        """
        try:
            logger.info(f"processing response: {cache_key}")

            parsed_data = self.parser.parse(response)

            if not parsed_data:
              raise DataParsingException

            parsed_record_data, query_metadata_info = self.data_extractor.extract(parsed_data)

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

            return ProcessedResponse(
                cache_key= cache_key,
                response = response,
                metadata = query_metadata_info,
                parsed_response = parsed_data,
                extracted_records = parsed_record_data,
                data = processed_response
            )

        except (DataParsingException, DataExtractionException, DataProcessingException,FieldNotFoundException) as e:
            logger.error(f"Error processing response: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during the processing of the response: {e}")

        return ProcessedResponse(
            cache_key = cache_key,
            response = response,
            data = None
            )

