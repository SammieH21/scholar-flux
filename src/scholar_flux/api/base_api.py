# /api/base_api.py
"""Defines the BaseAPI, which implements minimal features such as caching, requests, and response retrieval.

The BaseAPI is subclassed by scholar_flux.api.SearchAPI to further build and formulate requests based on the parameters
accepted by each API provider given their respective configurations.

"""
from typing import Optional, Dict, Any
import requests
from requests_cache import CachedSession
from urllib.parse import urljoin
import logging
from scholar_flux.exceptions import (
    RequestCreationException,
    SessionCreationError,
    APIParameterException,
)

from scholar_flux.sessions import SessionManager, CachedSessionManager
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.utils import config_settings

logger = logging.getLogger(__name__)


class BaseAPI:
    """The BaseAPI client is a minimal implementation for user-friendly request preparation and response retrieval.

    Args:
        session (Optional[requests.Session]): A pre-configured requests or requests-cache session.
                                              A new session is created if not specified.
        user_agent (Optional[str]): An optional user-agent string for the session.
        timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError
        use_cache (bool): Indicates whether or not to create a cached session. If a cached session is already
                          specified, this setting will have no effect on the creation of a session.

    Examples:
        >>> from scholar_flux.api import BaseAPI
        # creating a basic API client that uses the PLOS API as the default while caching response data in-memory:
        >>> base_api = BaseAPI(use_cache=True)
        # retrieve a basic request:
        >>> parameters = {'q': 'machine learning', 'start': 1, 'rows': 20}
        >>> response_page_1 = base_api.send_request('https://api.plos.org/search', parameters=parameters)
        >>> assert response_page_1.ok
        >>> response_page_1
        # OUTPUT: <Response [200]>
        >>> ml_page_1 = response_page_1.json()
        # retrieving the next page:
        >>> parameters['start'] = 21
        >>> response_page_2 = base_api.send_request('https://api.plos.org/search', parameters=parameters)
        >>> assert response_page_2.ok
        >>> response_page_2
        # OUTPUT: <Response [200]>
        >>> ml_page_2 = response_page_2.json()
        >>> ml_page_2
        # OUTPUT: {'response': {'numFound': '...', 'start': 21, 'docs': ['...']}} # redacted

    """

    DEFAULT_TIMEOUT: int = 20
    DEFAULT_USE_CACHE: bool = config_settings.get("SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND") is not None

    def __init__(
        self,
        user_agent: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: Optional[int | float] = None,
        use_cache: Optional[bool] = None,
    ):
        """Initializes the BaseAPI client for response retrieval given the provided inputs.

        The necessary attributes are prepared with a new or existing session (cached or uncached) via dependency
        injection. This class is designed to be subclassed for specific API implementations.

        Args:
            user_agent (Optional[str]): Optional user-agent string for the session.
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            timeout (Optional[int | float]): Timeout for requests in seconds.
            use_cache (Optional[bool]): Indicates whether or not to use cache. The default setting is to
                                        create a regular requests.Session unless a CachedSession is already provided.

        """
        self.session: requests.Session = self.configure_session(session, user_agent, use_cache)
        self.timeout = self._validate_timeout(timeout if timeout is not None else self.DEFAULT_TIMEOUT)

    @staticmethod
    def _validate_timeout(timeout: int | float) -> int | float:
        """Helper method used to ensure that timeout values received are non-negative numeric values."""
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise APIParameterException(f"Invalid timeout value: {timeout}")
        return timeout

    @property
    def user_agent(self) -> Optional[str]:
        """The User-Agent should always reflect what is used in the session.

        This method retrieves the User-Agent from the session directly.

        """
        user_agent = self.session.headers.get("User-Agent")
        return user_agent.decode("utf-8") if isinstance(user_agent, bytes) else user_agent

    @user_agent.setter
    def user_agent(self, user_agent: Optional[str]) -> None:
        """This property setter is used to directly update the session header without the need to update the user agent
        in both the session and the BaseAPI class.

        By updating the session User-Agent header, the user_agent property updates in addition.

        """
        if user_agent:
            self.session.headers.update(
                {"User-Agent": user_agent if not isinstance(user_agent, bytes) else user_agent.decode("utf-8")}
            )

    def configure_session(
        self,
        session: Optional[requests.Session] = None,
        user_agent: Optional[str] = None,
        use_cache: Optional[bool] = None,
    ) -> requests.Session:
        """
        Creates a session object if one does not already exist. If use_cache = True, then a cached session
        object will be used. A regular session that is not already cached will be overridden.

        Args:
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            user_agent (Optional[str]): Optional user-agent string for the session.
            use_cache (Optional[bool]): Indicates whether or not to use cache if a cached session doesn't yet exist.
                                        If `use_cache` is True and a cached session has already been passed, the
                                        previously created cached session is returned. Otherwise, a new CachedSession
                                        is created.

        Returns:
            requests.Session: The configured session.
        """
        try:

            if session is not None and not isinstance(session, requests.Session):
                raise APIParameterException(
                    f"Expected a requests.Session, a session subclass, or CachedSession, received {type(session)}"
                )

            headers = session.headers if isinstance(session, requests.Session) else {}

            if user_agent:
                headers["User-Agent"] = user_agent

            # caching is disabled by default if use_cache is not directly specified, a session is not specified,
            # and the DEFAULT_USE_CACHE class variable (which will only apply to new sessions) is set to False.

            if all(
                [
                    use_cache is True or (use_cache is None and self.DEFAULT_USE_CACHE is True),
                    not isinstance(session, CachedSession),
                ]
            ):
                logger.debug("Creating a cached session for the BaseAPI...")
                session = CachedSessionManager(
                    user_agent=user_agent,
                    backend=config_settings.get("SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND", "memory"),
                ).configure_session()

            # create a regular non-cached session and override only if `use_cache` is explicitly set to False
            if use_cache is False and isinstance(session, CachedSession):
                logger.debug("Removing session caching for the BaseAPI...")
                session = None

            # initialize a default session if session is not already created
            if not session:
                logger.debug("Creating a regular session for the BaseAPI...")
                session = SessionManager(user_agent=user_agent).configure_session()

            if headers:
                session.headers.update(headers)

            return session
        except Exception as e:
            logger.error("An unexpected error occurred during session initialization.")
            raise SessionCreationError(f"A new session could not be created successfully: {e}")

    def prepare_request(
        self,
        base_url: str,
        endpoint: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> requests.PreparedRequest:
        """Prepares a GET request for the specified endpoint with optional parameters.

        Args:
            base_url (str): The base URL for the API.
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            parameters (Optional[Dict[str, Any]]): Optional query parameters for the request.

        Returns:
            prepared_request (PreparedRequest) : The prepared request object.

        """
        try:
            url = urljoin(base_url, endpoint) if endpoint else base_url
            parameters = parameters or {}

            request = requests.Request("GET", url, params=parameters)
            prepared_request = request.prepare()
        except Exception as e:
            raise RequestCreationException(
                f"The request could not be prepared for base_url={base_url}, endpoint={endpoint}: {e}"
            )

        return prepared_request

    def send_request(
        self,
        base_url: str,
        endpoint: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[int | float] = None,
    ) -> requests.Response:
        """Sends a GET request to the specified endpoint with optional parameters.

        Args:
            base_url (str): The base API to send the request to.
            endpoint (Optional[str]): The endpoint of the API to send the request to.
            parameters (Optional[Dict[str, Any]]): Optional query parameters for the request.
            timeout (int): Timeout for the request in seconds.

        Returns:
            requests.Response: The response object.

        """

        timeout = self._validate_timeout(timeout if timeout is not None else self.timeout)

        prepared_request = self.prepare_request(base_url, endpoint, parameters)
        base_url = urljoin(base_url, endpoint) if endpoint else base_url

        logger.debug(f"Sending request to {base_url}")

        try:
            response = self.session.send(prepared_request, timeout=timeout)
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed for {base_url}: {e}")
            raise

    @staticmethod
    def _validate_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
        """Helper for validating parameters provided to the API at run-time: in the event that the parameters are valid,
        the function returns them as is. If not provided, None is returned.

        Args:
            parameters (dict[str, Any]): A dictionary of parameters to validate

        Returns:
            The original object that was provided, if no issues are found during validation

        Raises:
            APIParameterException: If the object is not a dictionary or contains a non-string key

        """
        if not isinstance(parameters, dict):
            raise APIParameterException(
                f"Expected the parameter overrides to be a dictionary, received type {type(parameters)}"
            )
        if any(not isinstance(param, str) for param in parameters):
            raise APIParameterException(
                f"Expected all parameter names to be strings. verify the types for each key: {parameters.keys()}"
            )
        return parameters

    def summary(self) -> str:
        """Create a summary representation of the current structure of the API:

        Returns the original representation.

        """
        return repr(self)

    def structure(self, flatten: bool = True, show_value_attributes: bool = False) -> str:
        """Base method for showing the structure of the current BaseAPI. This method reveals the configuration settings
        of the API client that will be used to send requests.

        Returns:
            str: The current structure of the BaseAPI or its subclass.

        """
        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Helper method for identifying the configuration for the BaseAPI."""
        return self.structure()


__all__ = ["BaseAPI"]
