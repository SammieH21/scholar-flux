from typing import Dict, Optional, Any, Annotated, Union, cast
from requests_cache.backends.base import BaseCache
from requests_cache import CachedSession
import logging
import time
import requests
from requests import Response
from scholar_flux import config
from scholar_flux.api import BaseAPI
from scholar_flux.api import APIParameterConfig, SearchAPIConfig
from scholar_flux.exceptions.api_exceptions import APIParameterException
import re
from urllib.parse import urlparse
logger = logging.getLogger(__name__)


class SearchAPI(BaseAPI):
    DEFAULT_URL:str = config.get('BASE_URL') or "https://api.plos.org/search"

    def __init__(self,
                 query: Annotated[str,"keyword:'{your search term}'"],
                 base_url: Annotated[str,"Valid URL for an Article API"] = DEFAULT_URL,
                 records_per_page:Annotated[int,"BETWEEN(1,100)"] = 20,
                 api_key: Annotated[Optional[str],"String Length: BETWEEN(20,200)"] = None,
                 session:Annotated[Optional[requests.Session],"A session/Cached Session object for making requests"] = None,
                 request_delay: Annotated[float,"Minimum time between requests: GT(0)"]=6-1,
                 parameter_config: Optional[APIParameterConfig] = None,
                 namespace: Annotated[Optional[str],"Non-empty Identifier"] = None,
                 **kwargs):
        """
        Initializes the SearchAPI with a query and optional parameters.
        Args:
            query (str): The search keyword or query string.
            base_url (str): The base URL for the article API.
            records_per_page (int): Number of records to fetch per page (1-100).
            api_key (Optional[str]): API key if required.
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            request_delay (Optional[float]): Minimum delay between requests in seconds.
            **kwargs: Additional keyword arguments for the API.
        """

        super().__init__(
                         #base_url=self.config.base_url,
                         #api_key=self.config.api_key,
                         session=session, **kwargs
        )

        # Create SearchAPIConfig internally with defaults and validation
        search_api_config = SearchAPIConfig(
            #query=query,
            base_url=base_url or SearchAPI.DEFAULT_URL,
            records_per_page=records_per_page,
            api_key=api_key,
            #request_delay=cast(float,request_delay),
            request_delay=request_delay,
        )

        self._initialize(query,
                         search_api_config=search_api_config,
                         parameter_config=parameter_config,
                         namespace=namespace)

    def _initialize(self,
                    query: str,
                    search_api_config:SearchAPIConfig,
                    parameter_config: Optional[APIParameterConfig] = None,
                    namespace: Optional[str] = None
                   ):
        """
        Initializes the API session with the provided base URL and API key.
        This method is called during the initialization of the class.
        """
        self.config=search_api_config
        url_basename = self.config.url_basename
        self.name=namespace or url_basename
        self.__query = query
        # self.query = self.config.query
        # self.api_key = self.config.api_key
        # self.records_per_page = self.config.records_per_page
        # self.request_delay:float = self.config.request_delay
        self.last_request: Optional[float] = None
        # first attempt to retrieve a non-empty parameter_config. If unsuccessful,
        # then whether the provided namespace or url matches a default provider
        self.parameter_config = parameter_config or \
                APIParameterConfig.get_defaults(self.name) or \
                APIParameterConfig.from_defaults(url_basename)

        if self.parameter_config.param_map.api_key_required and not self.config.api_key:
            logger.warning("API key is required but was not provided")

    @property
    def query(self) -> str:
        """
        Retrieves the current value of the query associated with the current API.
        """
        return self.__query

    @query.setter
    def query(self, query):
        """
        Uses the private method, __query to update the current query and uses
        validation to ensure that the query is a non empty string
        """
        if not query or not isinstance(query, str):
            raise ValueError(f"Query must be a non empty string., received empty string: {query}")
        self.__query = query

    @property
    def api_key(self) -> Optional[str]:
        return self.config.api_key
    @property
    def base_url(self) -> str:
        return self.config.base_url

    @property
    def records_per_page(self) -> int:
        return self.config.records_per_page

    @property
    def request_delay(self) -> float:
        return self.config.request_delay

    @classmethod
    def from_settings(cls, query: str,
                      config: SearchAPIConfig,
                      parameter_config: Optional[APIParameterConfig] = None,
                      namespace: Optional[str] = None,
                      **kwargs) -> "SearchAPI":
        """
        Advanced constructor: instantiate directly from a SearchAPIConfig instance.
        """

        instance = cls.__new__(cls)  # bypass __init__
        # Manually assign config and call super

        super(SearchAPI, instance).__init__(
            #base_url=config.base_url,
            #api_key=config.api_key,
            **kwargs,
        )

        instance._initialize(query,
                             search_api_config=config,
                             parameter_config=parameter_config,
                             namespace=namespace)
        return instance

    @classmethod
    def from_defaults(cls,
                   query: str,
                   provider_name: str,
                   records_per_page: Annotated[Optional[int],"BETWEEN(1,100)"] = None,
                   api_key: Optional[str] = None,
                   session: Optional[requests.Session] = None,
                   **kwargs) -> "SearchAPI":
        """
        Factory method to create SearchAPI instances with sensible defaults for known providers.
        """
        search_api_config = SearchAPIConfig.from_defaults(#query=query,
                                                   provider_name=provider_name,
                                                   records_per_page=records_per_page,
                                                   api_key=api_key)

        parameter_config = APIParameterConfig.from_defaults(provider_name)
        return cls.from_settings(query, config=search_api_config, parameter_config=parameter_config, session=session, **kwargs)

    @staticmethod
    def is_cached_session(session: Union[CachedSession,requests.Session]) -> bool:
        """
        Checks whether the given session is a cached session.

        Args:
            session (requests.Session): The session to check.

        Returns:
            bool: True if the session is a cached session, False otherwise.
        """
        cached_session = cast(CachedSession, session)
        return hasattr(cached_session, 'cache') and isinstance(cached_session.cache, BaseCache)

    @property
    def cache(self) -> Optional[BaseCache]:
        """
        Retrieves the session cache object if the session object is a CachedSession object.

        Returns:
            Optional[BaseCache]: The cache object if available, otherwise None.
        """
        if not self.session:
            return None

        cached_session = cast(CachedSession, self.session)
        cache = getattr(cached_session, 'cache', None)
        if isinstance(cache, BaseCache):
            return cache
        return None

    def build_params(self, page:int,**kwargs) -> Dict[str, Any]:
        """
        Constructs the request parameters for the API call.
        Args:
            page (int): The page number to request.
            **kwargs: Additional parameters for the request.
        Returns:
            Dict[str, Any]: The constructed request parameters.
        """
        # instanced parameters are generally static: thus page is the only parameter
        # Method to build request parameters
        params=self.parameter_config.build_params(query=self.query,
                                                   page = page,
                                                   records_per_page=self.records_per_page,
                                                   api_key=self.api_key,
                                                   **kwargs)

        return {k: v for k,v in params.items() if v is not None}

    def request_wait(self) -> None:
        """ determines how many seconds must elapse before making a request"""
        if self.last_request is not None:
            elapsed = time.time() - self.last_request
            delay = max(0, self.request_delay - elapsed)
            if delay > 0:
                logger.info(f"Waiting {delay} seconds before making another request...")
                time.sleep(delay)
        self.last_request = time.time()


    def make_request(self, current_page:int) -> Response:
        """Constructs and sends a request to the chosen api:
            The parameters are built based on the default/chosen
            config and parameter map
        Args:
            page (int): The page number to request.
        Returns:
            Response: The API's response to the request.
        """
        params = self.build_params(current_page)

        self.request_wait()
        response=self.send_request(self.base_url,params=params)

        return response

    def search(self, page: Optional[int] = None , params: Optional[Dict[str, Any]] = None) -> Response:
        """Public method to perform a search, by specifying either the page to query using the default parameters or by
           creating a custom request using a full dictionary containing the full set of parameters required."""

        if params is not None:
            self.request_wait()
            return self.send_request(self.base_url,params=params)
        elif page is not None:
            return self.make_request(page)
        else:
            raise APIParameterException("One of 'page' or 'params' must be provided")
