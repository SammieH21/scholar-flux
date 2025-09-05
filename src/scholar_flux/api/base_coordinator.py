from typing import Optional
import logging

from scholar_flux.api import SearchAPI, ResponseCoordinator
from scholar_flux.api.models import ResponseResult
from scholar_flux.exceptions import (
    RequestFailedException,
    InvalidCoordinatorParameterException,
)
from scholar_flux.data import BaseDataParser, BaseDataExtractor, ABCDataProcessor
from scholar_flux.utils.repr_utils import generate_repr_from_string

logger = logging.getLogger(__name__)


class BaseCoordinator:
    """
    Base coordinator providing the bare minimum functionality
    for requesting and retrieving records and metadata from APIs.

    This class uses dependency injection to orchestrate the process of constructing requests,
    validating response, and processing scientific works and articles. This class is designed
    to provide the absolute minimum necessary functionality to both retrieve and process data
    from APIs and can make use of caching functionality for caching requests and responses.
    """

    def __init__(
        self, search_api: SearchAPI, response_coordinator: ResponseCoordinator
    ):

        self._api: SearchAPI = search_api
        self._response_coordinator: ResponseCoordinator = response_coordinator
        self.last_response: Optional[ResponseResult] = None

    @property
    def parser(self) -> BaseDataParser:
        """Allows direct access to the data parser from the ResponseCoordinator"""
        return self.response_coordinator.parser

    @parser.setter
    def parser(self, parser: BaseDataParser) -> None:
        """Allows the direct modification of the data parser from the ResponseCoordinator"""
        self.response_coordinator.parser = parser

    @property
    def data_extractor(self) -> BaseDataExtractor:
        """Allows direct access to the DataExtractor from the ResponseCoordinator"""
        return self.response_coordinator.data_extractor

    @data_extractor.setter
    def data_extractor(self, data_extractor: BaseDataExtractor) -> None:
        """Allows the direct modification of the DataExtractor from the ResponseCoordinator"""
        self.response_coordinator.data_extractor = data_extractor

    @property
    def processor(self) -> ABCDataProcessor:
        """Allows direct access to the DataProcessor from the ResponseCoordinator"""
        return self.response_coordinator.processor

    @processor.setter
    def processor(self, processor: ABCDataProcessor) -> None:
        """Allows the direct modification of the DataProcessor from the ResponseCoordinator"""
        self.response_coordinator.processor = processor

    @property
    def api(self) -> SearchAPI:
        """Allows the search_api to be used as a property while also allowing for verification"""
        return self._api

    @api.setter
    def api(self, search_api: SearchAPI) -> None:
        """Allows the direct modification of the SearchAPI while ensuring type-safety"""
        if not isinstance(search_api, SearchAPI):
            raise InvalidCoordinatorParameterException(
                "Expected a SearchAPI object. "
                "Instead received type ({type(search_api)})"
            )
        self._api = search_api

    @property
    def response_coordinator(self) -> ResponseCoordinator:
        """Allows the response_coordinator to be used as a property while also allowing for verification"""
        return self._response_coordinator

    @response_coordinator.setter
    def response_coordinator(self, response_coordinator: ResponseCoordinator) -> None:
        """Allows the direct modification of the SearchAPI while ensuring type-safety"""
        if not isinstance(response_coordinator, ResponseCoordinator):
            raise InvalidCoordinatorParameterException(
                f"Expected a ResponseCoordinator object. "
                f"Instead received type ({type(response_coordinator)})"
            )
        self._response_coordinator = response_coordinator

    def search(self, **kwargs) -> Optional[ResponseResult]:
        """
        Public Search Method coordinating the retrieval and processing of an API response.
        This method serves as the base and will primarily handle the "How" of searching
        (e.g. Workflows, Single page search, etc.)
        """
        return self._search(**kwargs)

    def _search(self, **kwargs) -> Optional[ResponseResult]:
        """
        Basic Search Method implementing the core components needed to coordinate the
        the retrieval and processing of the response from the API
        Args:
            **kwargs: Arguments to provide to the search API
        Returns:
            Optional[ResponseResult]: Contains the raw response and information related to
            the basic processing of the data within theresponse
        """
        try:
            response = self.api.search(**kwargs)
            if response is not None:
                return self.response_coordinator.handle_response(
                    response, kwargs.get("cache_key")
                )
        except RequestFailedException as e:
            logger.error(
                f"Failed to get a valid response from the {self.api.provider_name} API: {e}"
            )
        return None

    def __repr__(self) -> str:
        """
        Method for identifying the current implementation and subclasses of the BaseCoordinator.
        Useful for showing the options being used to coordinate requests.
        """
        class_name = self.__class__.__name__
        attribute_dict = dict(
            api=repr(self.api), response_coordinator=self.response_coordinator
        )
        return generate_repr_from_string(class_name, attribute_dict)
