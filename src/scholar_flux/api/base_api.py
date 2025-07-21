
from typing import  List, Optional, Dict, Any
import requests
import logging
from string import punctuation
import re

logger = logging.getLogger(__name__)

class BaseAPI:
    def __init__(self,
                 user_agent: Optional[str] = None,
                 #api_key: Optional[str] = None,
                 session: Optional[requests.Session] = None):
        """
        Initializes the Base Api by defining the url that will contain the necessary setup logic to
        set up or use an existing session via dependency injection.
        This class is designed to be subclassed for specific API implementations.
        Args:
            base_url (str): The base URL for the API.
            user_agent (Optional[str]): Optional user-agent string for the session.
            api_key (Optional[str]): Optional API key for authentication.
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
        """

        #self.api_key: Optional[str] = api_key
        self.user_agent: Optional[str] = user_agent
        self.session: requests.Session = self.configure_session(session)

    def configure_session(self, session: Optional[requests.Session]) -> requests.Session:
        """
        Configures the session with optional user-agent and API key headers.

        Args:
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.

        Returns:
            requests.Session: The configured session.
        """
        session = session or requests.Session()
        if self.user_agent:
            session.headers.update({'User-Agent': self.user_agent})
        logger.info("API Session Initialization Successful.")
        return session

    def prepare_request(self, base_url: str, endpoint: Optional[str] = None, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None) -> requests.PreparedRequest:
        """
        Prepares a GET request for the specified endpoint with optional parameters.

        Argg::
            base_url (str): The base URL for the API.
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            params (Optional[Dict[str, Any]]): Optional query parameters for the request.

        Returns:
            prepared_request (PreparedRequest) : The prepared request object.
        """
        url = f"{base_url}/{endpoint}" if endpoint else base_url
        params = params or {}

        if api_key and not self._api_key_exists(params):
            params['api_key'] = api_key

        request = requests.Request('GET', url, params=params)
        prepared_request = request.prepare()
        return prepared_request

    def send_request(self, base_url: str, endpoint: Optional[str] = None, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> requests.Response:
        """
        Sends a GET request to the specified endpoint with optional parameters.

        Args:
            endpoint (Optional[str]): The API endpoint to send the request to.
            params (Optional[Dict[str, Any]]): Optional query parameters for the request.
            timeout (int): Timeout for the request in seconds.

        Returns:
            requests.Response: The response object.
        """
        prepared_request = self.prepare_request(base_url,endpoint, params)
        prepared_url = f'{base_url}/{endpoint}' if endpoint else base_url
        logger.debug(f"Sending request to {prepared_url}")

        response = self.session.send(prepared_request, timeout=timeout)
        return response

    @staticmethod
    def _api_key_exists(params: Dict[str, Any]) -> bool:
        """
        Helper method for determining whether an api key exists in the
        list of dict parameters provided to the request
        Args:
            params (Dict): Optional query parameters for the request.

        Returns:
            bool: Indicates whether or not an api key parameter exists
        """
        for k in params.keys():
            normalized = re.sub(rf"[{re.escape(punctuation)}]", "", k).lower()
            if normalized == 'apikey':
                return True
        return False
