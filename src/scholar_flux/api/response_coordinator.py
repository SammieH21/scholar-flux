# /api/response_coordinator.py
"""The scholar_flux.api.response_coordinator module implements the ResponseCoordinator that is used to coordinate the
processing of successfully and unsuccessfully retrieved responses. This class is used by the SearchCoordinator to
orchestrate the response parsing, processing and caching of responses.

The ResponseCoordinator relies on dependency injection to modify the processing methods used at each step.

"""
from __future__ import annotations
from scholar_flux.data_storage import DataCacheManager

from scholar_flux.data.base_parser import BaseDataParser
from scholar_flux.data.data_parser import DataParser
from scholar_flux.data.base_extractor import BaseDataExtractor
from scholar_flux.data.data_extractor import DataExtractor
from scholar_flux.data.abc_processor import ABCDataProcessor
from scholar_flux.data.pass_through_data_processor import PassThroughDataProcessor
from scholar_flux.utils.helpers import try_call

from scholar_flux.exceptions.api_exceptions import (
    InvalidResponseReconstructionException,
    InvalidResponseStructureException,
    RecordNormalizationException,
)

from scholar_flux.exceptions.data_exceptions import (
    DataParsingException,
    DataExtractionException,
    FieldNotFoundException,
    DataProcessingException,
)


from scholar_flux.utils.repr_utils import generate_repr_from_string
from scholar_flux.utils.helpers import generate_iso_timestamp, coerce_str
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.exceptions.coordinator_exceptions import (
    InvalidCoordinatorParameterException,
)
from scholar_flux.utils.record_types import RecordList
from scholar_flux.exceptions import StorageCacheException, MissingResponseException

from scholar_flux.api.models.responses import ProcessedResponse, ErrorResponse, APIResponse
from scholar_flux.api.response_validator import ResponseValidator

from requests.exceptions import RequestException
from typing import Any, cast
from requests import Response

import logging

logger = logging.getLogger(__name__)


class ResponseCoordinator:
    """Coordinates the parsing, extraction, processing, and caching of API responses. The ResponseCoordinator operates
    on the concept of dependency injection to orchestrate the entire process.

    Note that the overall composition of the coordinator is a governing factor in how the response is processed.
    The ResponseCoordinator uses a cache key and schema fingerprint to ensure that it is only
    returning a processed response from the cache storage if the structure of the coordinator at the time
    of cache storage has not changed.

    To ensure that we're not pulling from cache on significant changes to the ResponseCoordinator,
    we validate the schema by default using `DEFAULT_VALIDATE_FINGERPRINT`. When the schema changes,
    previously cached data is ignored, although this can be explicitly overridden during
    response handling.

    The coordinator orchestration process operates mainly through the ResponseCoordinator.handle_response
    method that sequentially calls the parser, extractor, processor, and cache_manager.

    Example workflow:

        >>> from scholar_flux.api import SearchAPI, ResponseCoordinator
        >>> api = SearchAPI(query = 'technological innovation', provider_name = 'crossref', user_agent = 'scholar_flux')
        >>> response_coordinator = ResponseCoordinator.build() # uses defaults with caching in-memory
        >>> response = api.search(page = 1)
        # future calls with the same structure will be cached
        >>> processed_response = response_coordinator.handle_response(response, cache_key='tech-innovation-cache-key-page-1')
        # the ProcessedResponse (or ErrorResponse) stores critical fields from the original and processed response
        >>> processed_response
        # OUTPUT: ProcessedResponse(len=20, cache_key='tech-innovation-cache-key-page-1', metadata=...)
        >>> new_processed_response = response_coordinator.handle_response(processed_response, cache_key='tech-innovation-cache-key-page-1')
        >>> new_processed_response
        # OUTPUT: ProcessedResponse(len=20, cache_key='tech-innovation-cache-key-page-1', metadata=...)

    Note that the entire process can be orchestrated via the SearchCoordinator that uses the SearchAPI and
    ResponseCoordinator as core dependency injected components:

        >>> from scholar_flux import SearchCoordinator
        >>> search_coordinator = SearchCoordinator(api, response_coordinator, cache_requests=True)
        # uses a default cache key constructed from the response internally
        >>> processed_response = search_coordinator.search(page = 1)
        # OUTPUT: ProcessedResponse(len=20, cache_key='crossref_technological innovation_1_20', metadata=...)
        >>> processed_response.content == new_processed_response.content


    Core Attributes:
        parser (BaseDataParser): Parses raw API responses.
        extractor (BaseDataExtractor): Extracts records and metadata.
        processor (ABCDataProcessor): Processes extracted data.
        cache_manager (DataCacheManager): Manages response cache.

    """

    DEFAULT_VALIDATE_FINGERPRINT: bool = True

    def __init__(
        self,
        parser: BaseDataParser,
        extractor: BaseDataExtractor,
        processor: ABCDataProcessor,
        cache_manager: DataCacheManager,
    ):
        """Initializes a ResponseCoordinator with specified components for response parsing, processing, and caching.

        Args:
            parser: (BaseDataParser):
                First step of the response processing pipeline: parses response records into a dictionary.
            extractor: (BaseDataExtractor):
                Extracts both records and metadata from an API response separately for future processing steps.
            processor: (ABCDataProcessor):
                Processes the list of dictionary-based records that were previously extracted from the APIResponse.
            cache_manager: (DataCacheManager):
                Manages the processed record caching for faster response processing for identical responses.

        """

        self.parser = parser
        self.extractor = extractor
        self.processor = processor
        self.cache_manager = cache_manager

    @classmethod
    def build(
        cls,
        parser: BaseDataParser | None = None,
        extractor: BaseDataExtractor | None = None,
        processor: ABCDataProcessor | None = None,
        cache_manager: DataCacheManager | None = None,
        cache_results: bool | None = None,
        annotate_records: bool | None = None,
    ) -> ResponseCoordinator:
        """Factory method to build a ResponseCoordinator with sensible defaults.

        Args:
            parser: (BaseDataParser):
                First step of the response processing pipeline: parses response records into a dictionary.
            extractor: (Optional[BaseDataExtractor]):
                Extracts both records and metadata from an API response separately for future processing steps.
            processor: (Optional[ABCDataProcessor]):
                Processes the list of dictionary-based records that were previously extracted from the APIResponse.
            cache_manager: (Optional[DataCacheManager]):
                Manages the processed record caching for faster response processing for identical responses.
            cache_results: (Optional[bool]):
                Determines whether or not to cache processed responses: Enabled by default unless specified or if a
                cache manager is already provided.
            annotate_records (Optional[bool]):
                When True, adds record-identifying linkage fields to each extracted record for resolution back to
                original data after processing or flattening. Adds `_extraction_index` (position) and `_record_id`
                (content hash + index). Default is None (no annotation).



        Returns:
            ResponseCoordinator: A fully constructed coordinator.

        """
        cache_manager = cls.configure_cache(cache_manager, cache_results)

        annotate_records = (
            annotate_records
            if annotate_records is not None
            else all([extractor is None, processor is not None, not isinstance(processor, PassThroughDataProcessor)])
        )

        return cls(
            parser=parser or DataParser(),
            extractor=extractor or DataExtractor(annotate_records=annotate_records),
            processor=processor or PassThroughDataProcessor(),
            cache_manager=cache_manager,
        )

    @classmethod
    def update(
        cls,
        response_coordinator: ResponseCoordinator,
        parser: BaseDataParser | None = None,
        extractor: BaseDataExtractor | None = None,
        processor: ABCDataProcessor | None = None,
        cache_manager: DataCacheManager | None = None,
        cache_results: bool | None = None,
        annotate_records: bool | None = None,
    ) -> ResponseCoordinator:
        """Factory method to create a new ResponseCoordinator from an existing configuration.

        Args:
            response_coordinator: (ResponseCoordinator):
                ResponseCoordinator containing the defaults to swap
            parser: (Optional[BaseDataParser]):
                First step of the response processing pipeline - parses response records into a dictionary
            extractor: (Optional[BaseDataExtractor]):
                Extracts both records and metadata from responses separately
            processor: (Optional[ABCDataProcessor]):
                Processes API responses into list of dictionaries
            cache_manager: (Optional[DataCacheManager]):
                Manages the caching of processed records for faster retrieval
            cache_results: (Optional[bool]):
                Determines whether or not to cache processed responses - on by default unless specified or if a cache
                manager is already provided
            annotate_records (Optional[bool]):
                When True, adds record-identifying linkage fields to each extracted record for resolution back to
                original data after processing or flattening. Adds `_extraction_index` (position) and `_record_id`
                (content hash + index). Default is None (no annotation).

        Returns:
            ResponseCoordinator: A fully constructed coordinator.

        """

        if not isinstance(response_coordinator, ResponseCoordinator):
            raise InvalidCoordinatorParameterException(
                "Expected a ResponseCoordinator to perform parameter updates. "
                f"Received type {type(response_coordinator)}"
            )

        extractor = extractor if extractor else response_coordinator.extractor
        updated_data_extractor = (
            DataExtractor.update(extractor, annotate_records=annotate_records)
            if annotate_records is not None
            else extractor
        )

        updated_cache_manager = cls.configure_cache(
            cache_manager if cache_manager is not None else response_coordinator.cache_manager,
            cache_results=cache_results,
        )

        return response_coordinator.build(
            parser=parser or response_coordinator.parser,
            extractor=updated_data_extractor,
            processor=processor or response_coordinator.processor,
            cache_manager=updated_cache_manager,
            cache_results=cache_results,
            annotate_records=annotate_records,
        )

    @classmethod
    def configure_cache(
        cls, cache_manager: DataCacheManager | None = None, cache_results: bool | None = None
    ) -> DataCacheManager:
        """Helper method for building and swapping out cache managers depending on the cache chosen.

        Args:
            cache_manager (Optional[DataCacheManager]): An optional cache manager to use
            cache_results (Optional[bool]): Ground truth parameter, used to resolve whether to use caching when the
                                            cache_manager and cache_results contradict

        Returns:
            DataCacheManager: An existing or newly created cache manager that can be used with the ResponseCoordinator

        """

        if cache_manager is not None and not isinstance(cache_manager, DataCacheManager):
            raise InvalidCoordinatorParameterException(
                f"Expected a Cache Manager for response processing, but received type: {type(cache_manager)}"
            )

        if cache_results is False:
            # Returns a no-op cache manager when cache_results is set to False
            cache_manager = DataCacheManager.null()
        elif cache_manager is None:
            # Generates a cache manager if it didn't already exist
            cache_manager = DataCacheManager()
        elif cache_manager.isnull() and cache_results is True:
            # Generate a cache manager cache_results is explicitly set to true and using a no-op manager
            cache_manager = DataCacheManager()

        return cache_manager

    @property
    def parser(self) -> BaseDataParser:
        """Allows direct access to the data parser from the ResponseCoordinator."""
        return self._parser

    @parser.setter
    def parser(self, parser: BaseDataParser) -> None:
        """Allows the direct modification of the data parser from the ResponseCoordinator."""
        if not isinstance(parser, BaseDataParser):
            raise InvalidCoordinatorParameterException(
                f"Expected a DataParser object. Instead received type ({type(parser)})"
            )
        self._parser = parser

    @property
    def extractor(self) -> BaseDataExtractor:
        """Allows direct access to the DataExtractor from the ResponseCoordinator."""
        return self._extractor

    @extractor.setter
    def extractor(self, extractor: BaseDataExtractor) -> None:
        """Allows the direct modification of the DataExtractor from the ResponseCoordinator."""
        if not isinstance(extractor, BaseDataExtractor):
            raise InvalidCoordinatorParameterException(
                f"Expected a DataExtractor object. " f"Instead received type ({type(extractor)})"
            )
        self._extractor = extractor

    @property
    def processor(self) -> ABCDataProcessor:
        """Allows direct access to the DataProcessor from the ResponseCoordinator."""
        return self._processor

    @processor.setter
    def processor(self, processor: ABCDataProcessor) -> None:
        """Allows the direct modification of the DataProcessor from the ResponseCoordinator."""
        if not isinstance(processor, ABCDataProcessor):
            raise InvalidCoordinatorParameterException(
                f"Expected a ABCDataProcessor or a sub-class of the "
                f"ABCDataProcessor. Instead received type ({type(processor)})"
            )
        self._processor = processor

    @property
    def cache(self) -> DataCacheManager:
        """Alias for the response data processing cache manager:

        Also allows direct access to the DataCacheManager from the ResponseCoordinator

        """
        return self._cache_manager

    @cache.setter
    def cache(self, cache_manager: DataCacheManager) -> None:
        """Alias for the response data processing cache manager:

        Also allows the direct modification of the DataCacheManager from the ResponseCoordinator

        """
        self.cache_manager = cache_manager

    @property
    def cache_manager(self) -> DataCacheManager:
        """Allows direct access to the DataCacheManager from the ResponseCoordinator."""
        return self._cache_manager

    @cache_manager.setter
    def cache_manager(self, cache_manager: DataCacheManager) -> None:
        """Allows the direct modification of the DataCacheManager from the ResponseCoordinator."""
        if not isinstance(cache_manager, DataCacheManager):
            raise InvalidCoordinatorParameterException(
                f"Expected a DataCacheManager or a subclass of the DataCacheManager. "
                f"Instead received type ({type(cache_manager)})"
            )
        self._cache_manager = cache_manager

    def handle_response_data(
        self, response: Response | ResponseProtocol, cache_key: str | None = None, **kwargs: Any
    ) -> RecordList | None:
        """Retrieves the data from the processed response from cache if previously cached. Otherwise the data is
        retrieved after processing the response.

        Args:
            response (Response | ResponseProtocol): Raw API response.
            cache_key (Optional[str]): Cache key for storing/retrieving.
            **kwargs: Additional keyword arguments to pass to `ResponseCoordinator.handle_response`.

        Returns:
            Optional[RecordList]: Processed response data or None.

        """

        # if caching is not in use, or the cache is not available or valid anymore, process:
        return self.handle_response(response, cache_key, **kwargs).data

    def handle_response(
        self,
        response: Response | ResponseProtocol,
        cache_key: str | None = None,
        from_cache: bool = True,
        validate_fingerprint: bool | None = None,
        normalize_records: bool | None = None,
    ) -> ErrorResponse | ProcessedResponse:
        """Handles response data extraction, processing, and caching, retrieving response data from cache if available.

        Once processed, the response data is transformed into a pydantic `ProcessedResponse` or `ErrorResponse` model
        that contains the response content, processing information, metadata, and/or error details when relevant.

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing/retrieving.
            from_cache: (bool): Indicates whether the response data should be retrieved from cache if available.
            validate_fingerprint: (Optional[bool]):
                Indicates whether cache should be invalidated if the `ResponseCoordinator` components are modified.
            normalize_records (Optional[bool]): Determines whether records should be normalized after processing.

        Returns:
            ProcessedResponse: A pydantic model containing the response data and detailed processing info.

        """
        cached_response = None

        if from_cache:
            # attempt to retrieve from cache first
            cached_response = self._from_cache(cache_key, response, validate_fingerprint)

        # if caching is not in use, or the cache is not available or valid anymore, process:
        return cached_response or self._handle_response(response, cache_key, normalize_records=normalize_records)

    def _from_cache(
        self,
        cache_key: str | None = None,
        response: Response | ResponseProtocol | None = None,
        validate_fingerprint: bool | None = None,
    ) -> ProcessedResponse | None:
        """Retrieves Previously Cached Response data that has been parsed, extracted, processed, and stored in cache.

        Args:
            response (Response | ResponseProtocol): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.

        Returns:
            Optional[ProcessedResponse]: Processed response data or None.

        """
        try:
            if not self.cache_manager:
                return None

            # determine whether we're actually using a response object
            response_obj = self._resolve_response(response, validate=True) if response is not None else None

            # ensure that we're either using a cache key from the defaults or creating one
            if not cache_key:
                logger.debug("A cache key was not specified. Attempting to create a cache key from the response...")
                cache_key = self.cache_manager.generate_fallback_cache_key(cast("ResponseProtocol", response_obj))

            # determine if the cache key created manually or directly from the response hash exists
            if not self.cache_manager.verify_cache(cache_key):
                return None

            # attempts to retrieve a cached response
            cached = self.cache_manager.retrieve(cache_key)

            if not (cached and self.cache_manager.cache_is_valid(cache_key, response_obj, cached)):
                return None

            if not self._validate_cached_schema(cached, validate_fingerprint):
                return None

            logger.info(f"retrieved response '{cache_key}' from cache")

            return self._rebuild_processed_response(
                cache_key=cache_key,
                response=response_obj,
                cached_response_dict=cached,
            )
        except (
            StorageCacheException,
            MissingResponseException,
            InvalidResponseReconstructionException,
            InvalidResponseStructureException,
        ) as e:
            logger.warning(
                f"An exception occurred while attempting to retrieve '{cache_key}' from cache: {e} Skipping Cache retrieval..."
            )
            return None

    @classmethod
    def _rebuild_processed_response(
        cls,
        cache_key: str,
        response: Response | ResponseProtocol | None = None,
        cached_response_dict: dict[str, Any] | None = None,
    ) -> ProcessedResponse:
        """Helper method for creating a processed response containing fields needed for processing."""
        if not isinstance(cached_response_dict, dict):
            logger.warning(
                f"A non-dictionary cache of type {type(cached_response_dict)} was encountered when rebuilding "
                "a ProcessedResponse from its components. Skipping retrieval of processed fields..."
            )
            cached_response_dict = {}

        # if a response object is not passed, but cache is available and stored in a dictionary
        # creates a new response from the serialized response, returning None if an error is encountered
        response = response or APIResponse.from_serialized_response(
            cached_response_dict.get("serialized_response"),
            status_code=cached_response_dict.get("status_code"),
            text=coerce_str(cached_response_dict.get("content")),
        )

        return ProcessedResponse(
            response=response,
            cache_key=cache_key,
            parsed_response=cached_response_dict.get("parsed_response"),
            extracted_records=cached_response_dict.get("extracted_records"),
            processed_records=cached_response_dict.get("processed_records"),
            normalized_records=cached_response_dict.get("normalized_records"),
            metadata=cached_response_dict.get("metadata"),
            created_at=cached_response_dict.get("created_at"),  # will perform internal validation
        )

    def _validate_cached_schema(
        self,
        cached_response_dict: dict[str, Any],
        validate_fingerprint: bool | None = None,
    ) -> bool | None:
        """Helper method for validating the cache dictionary containing the processed data, metadata, and other
        information for the current response."""
        if not cached_response_dict:
            return False

        cached_schema = cached_response_dict.get("schema")
        validate_fingerprint = (
            validate_fingerprint if validate_fingerprint is not None else self.DEFAULT_VALIDATE_FINGERPRINT
        )

        if validate_fingerprint and cached_schema:
            current_schema = self.schema_fingerprint()

            if cached_schema != current_schema:
                logger.info(
                    "The current schema does not match the previous schema that generated the "
                    f"previously cached response.\n\n Current schema: \n{current_schema}\n"
                    f"\nCached schema: \n{cached_schema}\n\n Skipping retrieval from cache."
                )
                return False
        return True

    @classmethod
    def _resolve_response(
        cls, response: Response | ResponseProtocol, validate: bool = False
    ) -> Response | ResponseProtocol:
        """Helper method for resolves and optionally validates the input as a response or response-like object.

         When received, this method unwraps `APIResponse`, `ProcessedResponse`, and `ErrorResponse`/`NonResponse`
         subclasses to resolve the raw response.

         If the raw response is a valid requests.Response or response-like object, the reconstructed response is
         returned as is. Otherwise, this method attempts to coerce the value into a `ReconstructedResponse`

         When coercion or validation fails, this method raises an `InvalidResponseStructureException` or the subclassed
         `InvalidResponseReconstructionException`.

        Args:
            response (Response | ResponseProtocol):
                A response or response-like object to resolve. response-like objects also include the
                `ReconstructedResponse` and `APIResponse` subclasses.
            validate (bool):
                Indicates whether to directly raise an error if the fields of the `ReconstructedResponse` are determined
                to be invalid.

        Returns:
            Response | ResponseProtocol: If the value is a valid response or response-like object

        Raises:
            InvalidResponseStructureException:
                If the object or its nested response is not a response-like object.
            InvalidResponseReconstructionException:
                If the values of the response or response-like object contain invalid values and validate is set to True

        """
        raw_response = response.response if isinstance(response, APIResponse) else response

        if isinstance(raw_response, Response) or ResponseValidator.is_valid_response_structure(raw_response):
            return raw_response

        # Attempts to coerce the current object into a response
        reconstructed_response = APIResponse.as_reconstructed_response(response)

        if validate:
            reconstructed_response.validate()

        return reconstructed_response

    def _handle_response(
        self,
        response: Response | ResponseProtocol,
        cache_key: str | None = None,
        normalize_records: bool | None = None,
    ) -> ErrorResponse | ProcessedResponse:
        """Parses, extracts, processes, and optionally caches response data and orchestrates the process of handling
        errors if one occurs anywhere along the response handling process.

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.
            normalize_records (Optional[bool]): Determines whether records should be normalized after processing

        Returns:
            ErrorResponse | ProcessedResponse:
                A pydantic model that contains response data and detailed processing info. Contains parsing,
                extraction, and processing information on success. Otherwise, on failure, an ErrorResponse is
                returned, detailing the precipitating factors behind the error.

        """

        try:
            resolved_response = self._resolve_response(response)
            resolved_response.raise_for_status()
            return self._process_response(resolved_response, cache_key, normalize_records=normalize_records)

        except (RequestException, InvalidResponseStructureException, InvalidResponseReconstructionException) as e:
            error_response = self._process_error(
                response, f"Error retrieving a valid response: {e}", e, cache_key=cache_key
            )

        except (
            DataParsingException,
            DataExtractionException,
            DataProcessingException,
            FieldNotFoundException,
        ) as e:
            error_response = self._process_error(
                response, f"Error processing the response: {e}", e, cache_key=cache_key
            )

        except Exception as e:
            error_response = self._process_error(
                response,
                f"An unexpected error occurred during the processing of the response: {e}",
                e,
                cache_key=cache_key,
            )

        return error_response

    def _process_response(
        self,
        response: Response | ResponseProtocol,
        cache_key: str | None = None,
        normalize_records: bool | None = None,
    ) -> ProcessedResponse:
        """Parses, extracts, processes, and optionally caches response data.

        Args:
            response (Response): A raw API response or response-like object.
            cache_key (Optional[str]): The cache key used for storing results for future retrieval.
            normalize_records (Optional[bool]): Determines whether records should be normalized

        Returns:
            ProcessedResponse:
                A pydantic model that contains response data and detailed processing info. Contains parsing,
                extraction, and processing information on success.

        """

        logger.info(f"processing response: {cache_key}")

        parsed_response_data = self.parser(response)

        if not parsed_response_data:
            raise DataParsingException("The parsed response contained no parsable content")

        extracted_records, metadata = self.extractor(parsed_response_data)

        processed_records = (
            self.processor(extracted_records) if extracted_records else ([] if extracted_records is not None else None)
        )

        creation_timestamp = generate_iso_timestamp()

        serialized_response = APIResponse.serialize_response(response)

        processed_response = ProcessedResponse(
            cache_key=cache_key,
            response=response,
            parsed_response=parsed_response_data,
            extracted_records=extracted_records,
            metadata=metadata,
            processed_records=processed_records,
            created_at=creation_timestamp,
        )

        if normalize_records and processed_response.url:
            normalized_records = (
                try_call(
                    processed_response.normalize,
                    kwargs=dict(update_records=True),
                    suppress=(RecordNormalizationException, TypeError, ValueError),
                )
                or None
            )
        else:
            normalized_records = None

        if cache_key and self.cache_manager:
            logger.debug("adding_to_cache")
            self.cache_manager.update_cache(
                cache_key,
                response,
                store_raw=True,
                metadata=metadata,
                parsed_response=parsed_response_data,
                extracted_records=extracted_records,
                processed_records=processed_records,
                normalized_records=normalized_records,
                serialized_response=serialized_response,
                schema=self.schema_fingerprint(),
                created_at=creation_timestamp,
            )
        logger.info("Data processed for %s", cache_key)

        return processed_response

    def _process_error(
        self,
        response: Response | ResponseProtocol,
        error_message: str,
        error_type: Exception,
        cache_key: str | None = None,
    ) -> ErrorResponse:
        """Creates and logs the processing error if one occurs during response processing.

        Args:
            response (Response): The raw API response.
            cache_key (Optional[str]): The cache key used for storing results.
            error_message (str): The error message describing the failure.
            error_type (Exception): The exception instance that was raised.

        Returns:
            ErrorResponse:
                A pydantic model containing the response, error data, and background information on what precipitated
                the error.

        """
        logger.error(error_message)

        return ErrorResponse.from_error(response=response, cache_key=cache_key, message=error_message, error=error_type)

    def schema_fingerprint(self) -> str:
        """Helper method for generating a concise view of the current structure of the response coordinator."""
        fingerprint = self.cache_manager.cache_fingerprint(
            generate_repr_from_string(
                self.__class__.__name__,
                dict(data_parser=self.parser, extractor=self.extractor, processor=self.processor),
                replace_numeric=True,
            )
        )

        return fingerprint

    def summary(self) -> str:
        """Helper class for creating a quick summary representation of the structure of the Response Coordinator."""
        class_name = self.__class__.__name__

        components = dict(
            parser=self.parser.__class__.__name__ + "(...)",
            extractor=self.extractor.__class__.__name__ + "(...)",
            processor=self.processor.__class__.__name__ + "(...)",
            cache_manager=self.cache_manager.structure(),
        )

        return generate_repr_from_string(class_name, components, flatten=True)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for retrieving a string representation of the overall structure of the current
        ResponseCoordinator. The helper function, generate_repr_from_string helps produce human-readable representations
        of the core structure of the ResponseCoordinator.

        Args:
            flatten (bool): Whether to flatten the ResponseCoordinator's structural representation into a single line.
            show_value_attributes (bool): Whether to show nested attributes of the components in the structure of the
                                          current ResponseCoordinator instance.

        Returns:
            str: The structure of the current ResponseCoordinator as a string.

        """
        class_name = self.__class__.__name__

        components = dict(
            parser=self.parser,
            extractor=self.extractor,
            processor=self.processor,
            cache_manager=self.cache_manager,
        )

        return generate_repr_from_string(
            class_name, components, flatten=flatten, show_value_attributes=show_value_attributes
        )

    def __repr__(self) -> str:
        """Helper class for representing the structure of the Response Coordinator."""
        return self.structure()


__all__ = ["ResponseCoordinator"]
