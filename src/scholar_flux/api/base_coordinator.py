# /api/base_coordinator.py
"""Defines the BaseCoordinator that implements the most basic orchestration components used to request, process, and
optionally cache processed record data from APIs."""
from typing import Optional
from typing_extensions import Self
import logging

from scholar_flux.api import SearchAPI, ResponseCoordinator
from scholar_flux.api.models import ProcessedResponse, ErrorResponse, ResponseHistoryRegistry
from scholar_flux.exceptions import (
    RequestFailedException,
    InvalidCoordinatorParameterException,
)

from scholar_flux.data.base_parser import BaseDataParser
from scholar_flux.data.base_extractor import BaseDataExtractor
from scholar_flux.data.abc_processor import ABCDataProcessor

from scholar_flux.utils.repr_utils import generate_repr_from_string

logger = logging.getLogger(__name__)


class BaseCoordinator:
    """BaseCoordinator providing the minimum functionality for requesting and retrieving records and metadata from APIs.

    This class uses dependency injection to orchestrate the process of constructing requests,
    validating responses, and processing scientific works and articles. This class is designed
    to provide the absolute minimum necessary functionality to both retrieve and process data
    from APIs and can make use of caching functionality for caching requests and responses.

    After initialization, the BaseCoordinator uses two main components for the sequential orchestration
    of response retrieval, processing, and caching.

    Components:
        SearchAPI (api/search_api):
            Handles the creation and orchestration of search requests in addition to the caching
            of successful requests via dependency injection.
        ResponseCoordinator (responses/response_coordinator): Handles the full range of response
            processing steps after retrieving a response from an API. These parsing, extraction,
            and processing steps occur sequentially when a new response is received. If a response
            was previously handled, the coordinator will attempt to retrieve these responses from
            the processing cache.

    Example:
        >>> from scholar_flux.api import SearchAPI, ResponseCoordinator, BaseCoordinator
        # Note: the SearchAPI uses PLOS by default if `provider_name` is not provided.
        # Unless the `SCHOLAR_FLUX_DEFAULT_PROVIDER` env variable is set to another provider.
        >>> base_search_coordinator = BaseCoordinator(search_api = SearchAPI(query = 'Math'),
        >>>                                           response_coordinator = ResponseCoordinator.build())
        >>> response = base_search_coordinator.search(page = 1)
        >>> response
        # OUTPUT <ProcessedResponse(len=20, cache_key=None, metadata="{'numFound': 14618, 'start': 1, ...})>
        # All processed records for a particular response can be found under response.data (a list of dictionaries)
        >>> list(response.data[0].keys())
        # OUTPUT ['article_type', 'eissn', 'id', 'journal', 'publication_date', 'score', 'title_display',
        #         'abstract', 'author_display']

    """

    _response_history: ResponseHistoryRegistry = ResponseHistoryRegistry()

    def __init__(self, search_api: SearchAPI, response_coordinator: ResponseCoordinator):
        """Initializes the base coordinator by delegating assignment of attributes to the _initialize method. Future
        coordinators can follow a similar pattern of using an _initialize for initial parameter assignment.

        Args:
            search_api (Optional[SearchAPI]):
                The search API to use for the retrieval of response records from APIs
            response_coordinator (Optional[ResponseCoordinator]):
                Core class used to handle the processing and core handling of all responses from APIs

        """
        self._initialize(search_api, response_coordinator)

    def _initialize(self, search_api: SearchAPI, response_coordinator: ResponseCoordinator):
        """Initializes the BaseCoordinator with a SearchApi and the constructed ResponseCoordinator."""
        self.search_api = search_api
        self.response_coordinator = response_coordinator

    @property
    def last_response(self) -> Optional[ProcessedResponse | ErrorResponse]:
        """Retrieves the last response sent to a provider."""
        return self._response_history.get(self.search_api.provider_name)

    @last_response.setter
    def last_response(self, response: ProcessedResponse | ErrorResponse) -> None:
        """Records the last response sent to a provider."""
        self._response_history.add(self.search_api.provider_name, response)

    @property
    def api(self) -> SearchAPI:
        """Alias for the underlying API used for searching."""
        return self.search_api

    @api.setter
    def api(self, search_api: SearchAPI) -> None:
        """Allows direct modification of the search API via the search_api alias."""
        self.search_api = search_api

    @property
    def search_api(self) -> SearchAPI:
        """Allows the search_api to be used as a property while also allowing for verification."""
        return self._search_api

    @search_api.setter
    def search_api(self, search_api: SearchAPI) -> None:
        """Allows the direct modification of the SearchAPI while ensuring type-safety."""
        if not isinstance(search_api, SearchAPI):
            raise InvalidCoordinatorParameterException(
                f"Expected a SearchAPI object. Instead received type ({type(search_api)})"
            )
        self._search_api = search_api

    @property
    def parser(self) -> BaseDataParser:
        """Allows direct access to the data parser from the ResponseCoordinator."""
        return self.response_coordinator.parser

    @parser.setter
    def parser(self, parser: BaseDataParser) -> None:
        """Allows the direct modification of the data parser from the ResponseCoordinator."""
        self.response_coordinator.parser = parser

    @property
    def extractor(self) -> BaseDataExtractor:
        """Allows direct access to the DataExtractor from the ResponseCoordinator."""
        return self.response_coordinator.extractor

    @extractor.setter
    def extractor(self, extractor: BaseDataExtractor) -> None:
        """Allows the direct modification of the DataExtractor from the ResponseCoordinator."""
        self.response_coordinator.extractor = extractor

    @property
    def processor(self) -> ABCDataProcessor:
        """Allows direct access to the DataProcessor from the ResponseCoordinator."""
        return self.response_coordinator.processor

    @processor.setter
    def processor(self, processor: ABCDataProcessor) -> None:
        """Allows the direct modification of the DataProcessor from the ResponseCoordinator."""
        self.response_coordinator.processor = processor

    @property
    def responses(self) -> ResponseCoordinator:
        """An alias for the response_coordinator property that is used for orchestrating the processing of retrieved API
        responses.

        Handles response orchestration, including response content parsing, the extraction of records/metadata, record
        processing, and cache operations.

        """
        return self.response_coordinator

    @responses.setter
    def responses(self, response_coordinator: ResponseCoordinator) -> None:
        """An alias for the response_coordinator property that allows direct modification of the ResponseCoordinator."""
        self.response_coordinator = response_coordinator

    @property
    def response_coordinator(self) -> ResponseCoordinator:
        """Allows the ResponseCoordinator to be used as a property.

        The response_coordinator handles and coordinates the processing of API responses from parsing, record/metadata
        extraction, processing, and cache management.

        """
        return self._response_coordinator

    @response_coordinator.setter
    def response_coordinator(self, response_coordinator: ResponseCoordinator) -> None:
        """Allows the direct modification of the ResponseCoordinator while ensuring type-safety."""
        if not isinstance(response_coordinator, ResponseCoordinator):
            raise InvalidCoordinatorParameterException(
                f"Expected a ResponseCoordinator object. Instead received type ({type(response_coordinator)})"
            )
        self._response_coordinator = response_coordinator

    def search(self, **kwargs) -> Optional[ProcessedResponse | ErrorResponse]:
        """Public Search Method coordinating the retrieval and processing of an API response.

        This method serves as the base and will primarily handle the "How" of searching (e.g. Workflows, Single page
        search, etc.)

        """
        return self._search(**kwargs)

    def parameter_search(
        self,
        **kwargs,
    ) -> Optional[ProcessedResponse | ErrorResponse]:
        """Public method for retrieving and processing non-paginated records with directly specified parameters.

        This method is designed as a direct entrypoint to performing searches without the addition of otherwise
        automatically populated, pagination-related fields such as `query`, `records_per_page`, etc. while still taking
        advantage of the orchestration features of the current coordinator.

        """
        # remove the `page` parameter to prevent potential errors
        kwargs.pop("page", None)
        return self._search(page=None, **kwargs)

    def _search(self, **kwargs) -> Optional[ProcessedResponse | ErrorResponse]:
        """
        Basic Search Method implementing the core components needed to coordinate the
        retrieval and processing of the response from the API
        Args:
            **kwargs: Arguments to provide to the search API
        Returns:
            Optional[ProcessedResponse | ErrorResponse]:
                Contains the raw response and information related to the basic processing
                of the data within the response
        """
        try:
            cache_key = kwargs.pop("cache_key", None)
            normalize_records = kwargs.pop("normalize_records", None)
            response = self.search_api.search(**kwargs)
            if response is not None:
                return self.response_coordinator.handle_response(
                    response, cache_key=cache_key, normalize_records=normalize_records
                )
        except RequestFailedException as e:
            logger.error(f"Failed to get a valid response from the {self.search_api.provider_name} API: {e}")
        return None

    @classmethod
    def as_coordinator(cls, search_api: SearchAPI, response_coordinator: ResponseCoordinator, *args, **kwargs) -> Self:
        """Helper factory method for building a SearchCoordinator that allows users to build from the final building
        blocks of a SearchCoordinator.

        Args:
            search_API (Optional[SearchAPI]):
                The search API to use for the retrieval of response records from APIs
            response_coordinator (Optional[ResponseCoordinator]):
                Core class used to handle the processing and core handling of all responses from APIs

        Returns:
            BaseCoordinator:
                A newly created coordinator subclassed from a BaseCoordinator that also orchestrates record retrieval
                and processing

        """
        search_coordinator = cls.__new__(cls)
        search_coordinator._initialize(search_api, response_coordinator, *args, **kwargs)
        return search_coordinator

    def summary(self) -> str:
        """Helper method for showing the structure of the current search coordinator."""
        class_name = self.__class__.__name__

        attributes = {
            "search_api": self.search_api.summary(),
            "response_coordinator": self.response_coordinator.summary(),
        }

        return generate_repr_from_string(class_name, attributes)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for quickly showing a representation of the overall structure of the SearchCoordinator. The
        helper function, generate_repr_from_string helps produce human-readable representations of the core structure of
        the Coordinator.

        Args:
            flatten (bool):
                Whether to flatten the coordinator's structural representation into a single line. Default=False
            show_value_attributes (bool):
                Whether to show nested attributes of the components of the BaseCoordinator its subclass.

        Returns:
            str: The structure of the current SearchCoordinator as a string.

        """
        class_name = self.__class__.__name__
        attribute_dict = dict(api=repr(self.search_api), response_coordinator=self.response_coordinator)
        return generate_repr_from_string(
            class_name, attribute_dict, flatten=flatten, show_value_attributes=show_value_attributes
        )

    def __repr__(self) -> str:
        """Method for identifying the current implementation and subclasses of the BaseCoordinator.

        Useful for showing the options being used to coordinate requests.

        """
        return self.structure()


__all__ = ["BaseCoordinator"]
