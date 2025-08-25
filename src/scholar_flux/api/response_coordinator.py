from scholar_flux.data_storage import DataCacheManager
from scholar_flux.data import BaseDataParser, BaseDataExtractor, ABCDataProcessor
from scholar_flux.exceptions.data_exceptions import (DataParsingException,
                                                     DataExtractionException,
                                                     FieldNotFoundException,
                                                     DataProcessingException)
from scholar_flux.utils.repr_utils import generate_repr_from_string
from scholar_flux.exceptions.coordinator_exceptions import InvalidCoordinatorParameterException
from scholar_flux.exceptions.storage_exceptions import StorageCacheException
from requests.exceptions import RequestException
from typing import Optional, Dict, List, Any
from requests import Response

import logging
logger = logging.getLogger(__name__)

from scholar_flux.api.models import ProcessedResponse, ErrorResponse


class ResponseCoordinator:
    """
    Coordinates the parsing, extraction, processing, and caching of API responses.

    Args:
        parser (BaseDataParser): Parses raw API responses.
        data_extractor (BaseDataExtractor): Extracts records and metadata.
        processor (ABCDataProcessor): Processes extracted data.
        cache_manager (DataCacheManager): Manages response cache.
    """

    def __init__(self,
                 parser:BaseDataParser,
                 data_extractor:BaseDataExtractor,
                 processor:ABCDataProcessor,
                 cache_manager: DataCacheManager):

        self.parser = parser
        self.data_extractor = data_extractor
        self.processor = processor
        self.cache_manager = cache_manager

    @property
    def parser(self)-> BaseDataParser:
        """Allows direct access to the data parser from the ResponseCoordinator"""
        return self._parser

    @parser.setter
    def parser(self, parser: BaseDataParser)-> None:
        """Allows the direct modification of the data parser from the ResponseCoordinator"""
        if not isinstance(parser, BaseDataParser):
            raise InvalidCoordinatorParameterException(
                f"Expected a DataParser object. Instead received type ({type(parser)})"
            )
        self._parser = parser

    @property
    def data_extractor(self) -> BaseDataExtractor:
        """Allows direct access to the DataExtractor from the ResponseCoordinator"""
        return self._data_extractor

    @data_extractor.setter
    def data_extractor(self, data_extractor: BaseDataExtractor)-> None:
        """Allows the direct modification of the DataExtractor from the ResponseCoordinator"""
        if not isinstance(data_extractor, BaseDataExtractor):
            raise InvalidCoordinatorParameterException(f"Expected a DataExtractor object. "
                                                       f"Instead received type ({type(data_extractor)})")
        self._data_extractor = data_extractor

    @property
    def processor(self)-> ABCDataProcessor:
        """Allows direct access to the DataProcessor from the ResponseCoordinator"""
        return self._processor

    @processor.setter
    def processor(self, processor: ABCDataProcessor) -> None:
        """Allows the direct modification of the DataProcessor from the ResponseCoordinator"""
        if not isinstance(processor, ABCDataProcessor):
            raise InvalidCoordinatorParameterException(f"Expected a ABCDataProcessor or a sub-class of the "
                                                       f"ABCDataProcessor. Instead received type ({type(processor)})")
        self._processor = processor

    @property
    def cache_manager(self)-> DataCacheManager:
        """Allows direct access to the DataCacheManager from the ResponseCoordinator"""
        return self._cache_manager

    @cache_manager.setter
    def cache_manager(self, cache_manager: DataCacheManager)-> None:
        """Allows the direct modification of the DataCacheManager from the ResponseCoordinator"""
        if not isinstance(cache_manager, DataCacheManager):
            raise InvalidCoordinatorParameterException(
                f"Expected a DataCacheManager or a sub-class of the ABCDataProcessor. "
                f"Instead received type ({type(cache_manager)})"
            )
        self._cache_manager = cache_manager

    def handle_response_data(self,
                             response: Response,
                             cache_key: Optional[str] = None) -> Optional[List[Dict[Any, Any]] | List]:
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
                        from_cache: bool = True) ->  ErrorResponse | ProcessedResponse:
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
        return cached_response or self._handle_response(response, cache_key)


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


    def _handle_response(self, response: Response, cache_key: Optional[str] = None)-> ErrorResponse | ProcessedResponse:
        """
        Parses, extracts, processes, and optionally caches response data and orchestrates the process of handling errors
        if one occurs anywhere along the response hanlding preocess.

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.

        Returns:
            ErrorResponse | ProcessedResponse: A Dataclass Object that contains response data
                                               and detailed processing info. Contains
                                               parsing, extraction, and processing information on
                                               success. Otherwise, on failure, an ErrorResponse is
                                               returned, detailing the precipitating factors behind the
                                               error.

        """
        try:
            response.raise_for_status()
            return self._process_response(response, cache_key)

        except RequestException as e:
            error_response = self._process_error(response, f"Error retrieving response {e}", e, cache_key = cache_key)

        except (DataParsingException, DataExtractionException, DataProcessingException,FieldNotFoundException) as e:
            error_response = self._process_error(response, f"Error processing response {e}", e, cache_key = cache_key)

        except Exception as e:
            error_response = self._process_error(
                response, f"An unexpected error occurred during the processing of the response: {e}",
                e, cache_key = cache_key
            )

        return error_response

    def _process_response(self, response: Response, cache_key: Optional[str] = None)-> ProcessedResponse:
        """
        Parses, extracts, processes, and optionally caches response data.

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.

        Returns:
            ProcessedResponse: A Dataclass Object that contains response data
                               and detailed processing info. Contains
                               parsing, extraction, and processing information on
                               success.
        """

        logger.info(f"processing response: {cache_key}")

        parsed_response_data = self.parser(response)

        if not parsed_response_data:
          raise DataParsingException

        extracted_records, metadata = self.data_extractor(parsed_response_data)

        processed_response = self.processor(extracted_records) if extracted_records else None

        if cache_key and self.cache_manager:
            logger.debug("adding_to_cache")
            self.cache_manager.update_cache(cache_key,
                                            response,
                                            store_raw=True,
                                            metadata=metadata,
                                            parsed_response=parsed_response_data,
                                            extracted_records=extracted_records,
                                            processed_response=processed_response)
        logger.info("Data processed for %s",cache_key)

        return ProcessedResponse(
            cache_key = cache_key,
            response = response,
            parsed_response = parsed_response_data,
            extracted_records = extracted_records,
            metadata = metadata,
            data = processed_response
        )


    def _process_error(self, response: Response,
                       error_message: str,
                       error_type: Exception,
                       cache_key: Optional[str] = None)-> ErrorResponse:
        """
        Creates and logs the processing error if one occurs during response processing

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.

        Returns:
            ErrorResponse: A Dataclass Object that contains the error response data
                            and background information on what precipitated the error.
        """
        logger.error(error_message)

        return ErrorResponse(
            cache_key = cache_key,
            response = response,
            message = error_message,
            error = type(error_type).__name__
        )


    def __repr__(self) -> str:
        """Helper class for representing the structure of the Response Coordinator"""
        class_name = self.__class__.__name__

        components = dict(parser = self.parser,
                          data_extractor = self.data_extractor,
                          processor = self.processor,
                          cache_manager = self.cache_manager)

        return generate_repr_from_string(class_name, components)

