from typing import Dict, Optional, Any, Annotated, Union
from typing import cast
from requests_cache.backends.base import BaseCache
from requests_cache import CachedSession
import logging
import time
import requests
from requests import Response
from .. import config
from . import BaseAPI
from . import APIParameterConfig
import re
from urllib.parse import urlparse
logger = logging.getLogger(__name__)



 
class SearchAPI(BaseAPI):
    DEFAULT_REQUEST_DELAY=6.1
    DEFAULT_URL:str = config.get('BASE_URL') or "https://api.plos.org/search"
    def __init__(self,
                 query: Annotated[str,"keyword:'{your search term}'"],
                 base_url: Annotated[str,"Valid URL for an Article API"] = DEFAULT_URL,
                 records_per_page:Annotated[int,"BETWEEN(1,100)"] = 100,
                 api_key: Annotated[Optional[str],"Length: BETWEEN(20,200)"] = None,
                 session:Annotated[Optional[requests.Session],"A session/Cached Session object for making requests"] = None,
                 request_delay: Annotated[Optional[float],"Minimum time between requests: GT(0)"]=None,
                 parameter_config: Optional[APIParameterConfig] = None,
                 **kwargs):

        super().__init__(base_url=base_url, api_key=api_key,session=session, **kwargs)

        

        self.name=self.extract_main_site(base_url)
        self.query = query
        self.records_per_page = records_per_page
        self.last_request: Optional[float] = None
        self.request_delay:float = self._validate_request_delay(request_delay, self.DEFAULT_REQUEST_DELAY)
        self.cached=self.is_cached_session(self.session)
        self.parameter_config = parameter_config or APIParameterConfig.from_defaults(self.name)

    @staticmethod
    def extract_main_site(url: str) -> str:
        """
        Extracts the main site name from a URL by removing everything before 'www' and everything
        including and after the top-level domain.

        Args:
            url (str): The URL to process.

        Returns:
            str: The main site name.
        """
        # Parse the URL to extract the hostname
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        
        if not hostname:
            # Handle case when urlparse fails to get hostname
            hostname = url.split('/')[0]

        # Regular expression to match the main site name in the hostname
        pattern = re.compile(r'^(?:.*\.)?([a-zA-Z0-9-_]+)\.(?:com|org|net|io|gov|edu)')
        match = pattern.search(hostname)
        
        if match:
            return match.group(1)
        else:
            return ""

    @staticmethod
    def _validate_request_delay(delay: Optional[float],default: float) -> float:
        """
        Validates the request delay value without enforcing a delay.

        Raises:
            ValueError: If the request_delay is not a positive number.
        """
        # Validate the request_delay value here without enforcing a delay
        if delay is None:
            return default
        try:
            request_delay = float(delay)
            if request_delay < 0:
                raise ValueError(f"request_delay must be a positive number, got {delay}")
            return request_delay
        except ValueError as e:
            logger.error(f"Invalid 'request_delay': {e}. Using the default setting: request delay = {default}")
            return default

    @staticmethod
    def is_cached_session(session: requests.Session) -> bool:
        """
        Checks whether the given session is a cached session.

        Args:
            session (requests.Session): The session to check.

        Returns:
            bool: True if the session is a cached session, False otherwise.
        """
        cached_session = cast(CachedSession, session)
        return hasattr(cached_session, 'cache') and isinstance(cached_session.cache, BaseCache)

    def _build_params(self, page:int) -> Dict[str, Any]:
        # instanced parameters are generally static: thus page is the only parameter
        # Method to build request parameters
        params=self.parameter_config._build_params(query=self.query,
                                                   page = page,
                                                   records_per_page=self.records_per_page,
                                                   api_key=self.api_key)

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
            
    
    def make_request(self, current_page:int,**kwargs) -> Response:
        """Constructs and sends a request to the Springer or SolR api's that use a consistent key format."""
        self.request_wait()
        params = self._build_params(current_page)               

        #cache_key = self._create_cache_key(page)    
        response=self.send_request(params=params,**kwargs)
        
        return response
    
    def search(self, page: Optional[int] = None , params: Optional[Dict[str, Any]] = None) -> Response:
        """Public method to perform a search, by specifying either the page to query using the default parameters or by
           creating a custom request using a full dictionary containing the full set of parameters required."""

        if params is not None:
            return self.send_request(params=params)
        elif page is not None:
            return self.make_request(page)
        else:
            raise ValueError("One of 'page' or 'params' must be provided")
           
#   def _calculate_start(self, page):
#       """Calculates the starting item index for a given page."""
#       return 1 + (page - 1) * self.records_per_page
#   
#   def _build_params(self, page):
#       # Method to build request parameters
#       record_start = self._calculate_start(page)
#       return {
#           'q': self.query,
#           'api_key': self.api_key,
#           'p': self.records_per_page,  # records per page
#           's': record_start  # starting item index
#       }
#   @staticmethod
#   def _validate_request_delay(delay):
#       """
#       Validates the request delay value without enforcing a delay.

#       Raises:
#           ValueError: If the request_delay is not a positive number.
#       """
#       # Validate the request_delay value here without enforcing a delay
#       try:
#           request_delay = float(delay)
#           if delay < 0:
#               raise ValueError(f"request_delay must be a positive number, got {delay}")
#       except ValueError as e:
#           logger.error(f"Invalid 'request_delay': {e}. Using the default setting")
#           return None
#       return delay
#           
#       
#   def request_wait(self):
#       """ determines how many seconds must elapse before making a request"""
#       if self.last_request is not None:
#           elapsed = time.time() - self.last_request
#           delay = max(0, self.request_delay - elapsed)
#           if delay > 0:
#               logger.info(f"Waiting {delay} seconds before making another request...")
#               time.sleep(delay)
#       self.last_request = time.time()
    
 


#   def _create_cache_key(self,page):
#       """
#       Combines information about the query type and current page to create an identifier for the current query.

#       Args:
#               page (int): The current page number.

#       Returns:
#       str: A unique cache key based on the provided parameters.
#       """
#       
#       return f"{self.query}_{page}_{self.records_per_page}"
    
    
#user_agent: Annotated[Optional[str],"Display user agent when sending requests"]=None,
    # def _configure_session(self,secret,encrypt,enable_cache):
    #     # Example condition to decide whether to use caching; this could be based on config or explicit user choice
    #     logger.info("configuring cache")
    #     if enable_cache:
    #         try:
    #             manager=SessionManager(encrypt=encrypt,user_agent=self.user_agent,cache_name="search_requests_cache",secret=secret,cached=enable_cache)
    #             logger.info('Creating Cached Session')
    #             return(manager.configure_session())
    #         except ValueError as e:
    #             logger.warning("%s.. Creating the default requests session...",e)
    #     return requests.Session()


