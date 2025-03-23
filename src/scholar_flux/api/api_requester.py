
from typing import  List, Optional, Dict, Any
import requests
import logging

logger = logging.getLogger(__name__)

class BaseAPI:
    def __init__(self, base_url: str, user_agent: Optional[str] = None, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.base_url: str = base_url
        self.api_key: Optional[str] = api_key
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

    def prepare_request(self, endpoint: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        """
        Prepares a GET request for the specified endpoint with optional parameters.

        Args:
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            params (Optional[Dict[str, Any]]): Optional query parameters for the request.

        Returns:
            prepared_request (PreparedRequest)
        """
        url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
        params = params or {}
        if self.api_key:
            params['api_key'] = self.api_key  # Ensure the API key is included if specified
        request = requests.Request('GET', url, params=params)
        prepared_request = request.prepare()
        return prepared_request

    def send_request(self, endpoint: Optional[str] = None, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> requests.Response:
        """
        Sends a GET request to the specified endpoint with optional parameters.

        Args:
            endpoint (Optional[str]): The API endpoint to send the request to.
            params (Optional[Dict[str, Any]]): Optional query parameters for the request.
            timeout (int): Timeout for the request in seconds.

        Returns:
            requests.Response: The response object.
        """
        prepared_request = self.prepare_request(endpoint, params)
        logger.debug(f"Sending request to {prepared_request.url}")
        response = self.session.send(prepared_request, timeout=timeout)
        return response

#    def send_request(self, endpoint: Optional[str] = None, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> requests.Response:
#        """
#        Sends a GET request to the specified endpoint with optional parameters.
#
#        Args:
#            endpoint (Optional[str]): The API endpoint to send the request to.
#            params (Optional[Dict[str, Any]]): Optional query parameters for the request.
#            timeout (int): Timeout for the request in seconds.
#
#        Returns:
#            requests.Response: The response object.
#        """
#        url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
#        params = params or {}
#        if self.api_key:
#            params['api_key'] = self.api_key  # Ensure the API key is included if specified
#        logger.debug(f"Sending request to {url} with params {params}")
#        return self.session.get(url, params=params, timeout=timeout)

