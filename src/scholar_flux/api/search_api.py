from __future__ import annotations
from typing import Dict, Optional, Any, Annotated, Union, cast, Iterator
from contextlib import contextmanager
from requests_cache.backends.base import BaseCache
from requests_cache import CachedSession
from pydantic import SecretStr
import logging
import requests
from requests import Response
from scholar_flux import config, masker as default_masker
from scholar_flux.api import BaseAPI, APIParameterConfig, SearchAPIConfig, RateLimiter
from scholar_flux.api.providers import provider_registry
from scholar_flux.exceptions.api_exceptions import (
    APIParameterException,
    QueryValidationException,
    RequestCreationException,
)
from scholar_flux.security import SensitiveDataMasker, SecretUtils
from scholar_flux.utils.repr_utils import generate_repr_from_string
from pydantic import ValidationError
import re
from urllib.parse import urljoin
from string import punctuation

logger = logging.getLogger(__name__)


class SearchAPI(BaseAPI):
    DEFAULT_URL: str = "https://api.plos.org/search"
    DEFAULT_CACHED_SESSION: bool = False

    def __init__(
        self,
        query: Annotated[str, "keyword:'{your search term}'"],
        base_url: Annotated[Optional[str], "Valid URL for an Article API"] = None,  # SearchAPIConfig
        api_key: Annotated[
            Optional[str | SecretStr],
            "An API key for providers requiring identification of users",
        ] = None,  # SearchAPIConfig
        parameter_config: Optional[APIParameterConfig] = None,
        provider_name: Annotated[
            Optional[str],
            "The name of the API Provider. Can be provided in place of a base_url",
        ] = None,
        session: Annotated[
            Optional[requests.Session | CachedSession],
            "A session/Cached Session object for making requests",
        ] = None,
        user_agent: Annotated[Optional[str], "An optional User-Agent to associate with each search"] = None,
        timeout: Annotated[
            Optional[int | float],
            "Number of seconds that must elapse before the request times out",
        ] = None,
        masker: Optional[SensitiveDataMasker] = None,
        records_per_page: Annotated[int, "BETWEEN(1,100)"] = 20,  # SearchAPIConfig
        request_delay: Annotated[float, "Minimum time between requests: GT(0)"] = 6 - 1,  # SearchAPIConfig
        use_cache: Annotated[Optional[bool], "Indicate whether to use a simple in-memory session cache"] = None,
        **api_specific_parameters,  # SearchAPIConfig
    ):
        """
        Initializes the SearchAPI with a query and optional parameters. The absolute bare minimum for interacting with APIs
        requires a query, base_url, and an APIParameterConfig that associates relevant fields (aka query, records_per_page,
        etc. with fields that are specific to each API provider.

        Args:
            query (str): The search keyword or query string.
            base_url (str): The base URL for the article API.
            records_per_page (int): Number of records to fetch per page (1-100).
            api_key (Optional[str | SecretStr]): API key if required.
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            user_agent (Optional[str]): Optional user-agent string for the session.
            masker (Optional[str]): Used for filtering potentially sensitive information from logs
                                    (API keys, auth bearers, emails, etc)
            request_delay (Optional[float]): Minimum delay between requests in seconds.
            use_cache (bool): Indicates whether or not to create a cached session. If a cached session is already
                                   specified, this
            **api_specific_parameters: Additional parameter-value pairs to be provided to SearchAPIConfig class:
                API specific parameters include:
                    mailto (Optional[str | SecretStr]): (CROSSREF: an optional contact for feedback on API usage)
                    db: str (PUBMED: a database to retrieve data from (example: db=pubmed)
        """

        super().__init__(session=session, timeout=timeout, user_agent=user_agent, use_cache=use_cache)

        # Create SearchAPIConfig internally with defaults and validation
        try:

            # if neither the provider nor a base url is provided, fall back to using the default URL
            if not base_url and not provider_name:
                base_url = self.DEFAULT_URL

            search_api_config = SearchAPIConfig(
                base_url=base_url or "",
                provider_name=provider_name or "",
                records_per_page=records_per_page,
                api_key=SecretUtils.mask_secret(api_key),
                request_delay=request_delay,
                **api_specific_parameters,
            )

        except (NotImplementedError, ValidationError, APIParameterException) as e:
            raise APIParameterException(f"Invalid SearchAPIConfig: {e}") from e

        self._initialize(
            query,
            search_api_config=search_api_config,
            parameter_config=parameter_config,
            masker=masker,
        )

    def _initialize(
        self,
        query: str,
        search_api_config: SearchAPIConfig,
        parameter_config: Optional[APIParameterConfig] = None,
        masker: Optional[SensitiveDataMasker] = None,
    ):
        """
        Initializes the API session with the provided base URL and API key.
        This method is called during the initialization of the class.

        Args:
            query (str): The query to send to the current API provider. Note, this must be nonmissing
            config (SearchAPIConfig): Indicates the configuration settings to be used when sending requests to APIs
            parameter_config: Optional[APIParameterConfig] = Maps global scholar_flux parameters to those that
                                                             are specific to the provider's API
            session:(Optional[requests.Session | CachedSession]): An optional session to use for the creation
                                                                  of request sessions
            timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError

        """
        self.config = search_api_config
        self.query = query
        self.last_request: Optional[float] = None
        self._rate_limiter = RateLimiter(min_interval=self.config.request_delay)
        self.masker = masker or default_masker

        # first attempt to retrieve a non-empty parameter_config. If unsuccessful,
        # then whether the provided namespace or url matches a default provider
        self.parameter_config = parameter_config or APIParameterConfig.from_defaults(self.provider_name)

        if self.parameter_config.parameter_map.api_key_required and not self.config.api_key:
            logger.warning("API key is required but was not provided")
        logger.debug("Initialized a new SearchAPI Session Successfully.")

    @property
    def config(self) -> SearchAPIConfig:
        """
        Property method for accessing the config for the SearchAPI

        Returns:
            The configuration corresponding to the API Provider
        """
        return self._config

    @config.setter
    def config(self, _config: SearchAPIConfig) -> None:
        """
        Used to ensure that assignments and updates to the SearchAPI configuration will work as intended.
        It first validates the configuration for the search api, and assigns the value if it is
        a SearchAPIConfig element.

        Args:
            _config (SearchAPIConfig): The configuration to assign to the SearchAPI instance

        Raises:
            APIParameterException: Indicating that the provided value is not a SearchAPIConfig
        """
        if not isinstance(_config, SearchAPIConfig):
            raise APIParameterException(f"Expected a SearchAPIConfig, received type: {type(_config)}")
        self._config = _config

    @property
    def parameter_config(self) -> APIParameterConfig:
        """
        Property method for accessing the parameter mapping config for the SearchAPI

        Returns:
            The configuration corresponding to the API Provider
        """
        return self._parameter_config

    @parameter_config.setter
    def parameter_config(self, _parameter_config: APIParameterConfig) -> None:
        """
        Used to ensure that assignments and updates to the SearchAPI configuration will work as intended.
        It first validates the configuration for the search api, and assigns the value if it is
        a SearchAPIConfig element.

        Args:
            _config (APIParameterConfig): The parameter mapping configuration to assign to the SearchAPI instance

        Raises:
            APIParameterException: Indicating that the provided value is not a APIParameterConfig
        """
        if not isinstance(_parameter_config, APIParameterConfig):
            raise APIParameterException(f"Expected an APIParameterConfig, received type: {type(_parameter_config)}")
        self._parameter_config = _parameter_config

    @property
    def provider_name(self) -> str:
        """
        Property method for accessing the provider name in the current SearchAPI instance.

        Returns:
            The name corresponding to the API Provider.
        """
        return self.config.provider_name

    @property
    def query(self) -> str:
        """
        Retrieves the current value of the query to be sent to the current API.
        """
        return self.__query

    @query.setter
    def query(self, query):
        """
        Uses the private method, __query to update the current query and uses
        validation to ensure that the query is a non-empty string
        """
        if not query or not isinstance(query, str):
            raise QueryValidationException(f"Query must be a non empty string., received empty string: {query}")
        self.__query = query

    @property
    def api_key(self) -> Optional[SecretStr]:
        """
        Retrieves the current value of the API key from the SearchAPIConfig.
        Note that the api key is stored as a secret key when available

        Returns:
            Optional[SecretStr]: A secret string of the API key if it exists
        """
        return self.config.api_key

    @property
    def base_url(self) -> str:
        """
        Corresponds to the base url of the currrent API

        Returns:
            The base url corresponding to the API Provider
        """
        return self.config.base_url

    @property
    def records_per_page(self) -> int:
        """
        Indicates the total number of records to show on each page.

        Returns:
            int: an integer indicating the max number of records per page
        """
        return self.config.records_per_page

    @property
    def request_delay(self) -> float:
        """
        Indicates how long we should wait in-between requests. Useful due
        to comply with the rate-limiting requirements of various APIs

        Returns:
            float: The number of seconds to wait at minimum between each request
        """
        return self.config.request_delay

    @property
    def api_specific_parameters(self) -> dict:
        """
        This property pulls additional parameters corresponding to the API from the
        configuration of the current API instance
        Returns:
            dict[str, APISpecificParameter]: A list of all parameters specific to the current API.
        """
        return self.config.api_specific_parameters or {}

    @classmethod
    def from_settings(
        cls,
        query: str,
        config: SearchAPIConfig,
        parameter_config: Optional[APIParameterConfig] = None,
        session: Optional[requests.Session | CachedSession] = None,
        timeout: Optional[int | float] = None,
        use_cache: Optional[bool] = None,
        masker=None,
        user_agent: Optional[str] = None,
    ) -> "SearchAPI":
        """
        Advanced constructor: instantiate directly from a SearchAPIConfig instance.

        Args:
            config (SearchAPIConfig): Indicates the configuration settings to be used when sending requests to APIs
            parameter_config: Optional[APIParameterConfig] = Maps global scholar_flux parameters to those that
                                                             are API specific
            session:(Optional[requests.Session | CachedSession]): An optional session to use for the creation
                                                                  of request sessions
            timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError
        """

        # bypass __init__
        instance = cls.__new__(cls)
        # Manually assign config and call super

        # initializes the base class and it's methods/session settings
        super(SearchAPI, instance).__init__(
            session=session, timeout=timeout, user_agent=user_agent, use_cache=use_cache
        )

        # initializes all remaining settings (e.g. mask, query, configs, rate limiter)
        instance._initialize(
            query,
            search_api_config=config,
            parameter_config=parameter_config,
            masker=masker,
        )
        return instance

    @classmethod
    def from_defaults(
        cls,
        query: str,
        provider_name: Optional[str],
        session: Optional[requests.Session] = None,
        user_agent: Annotated[Optional[str], "An optional User-Agent to associate with each search"] = None,
        use_cache: Optional[bool] = None,
        timeout: Optional[int | float] = None,
        masker: Optional[SensitiveDataMasker] = None,
        **api_specific_parameters,
    ) -> "SearchAPI":
        """
        Factory method to create SearchAPI instances with sensible defaults for known providers. PLOS is used by default
        unless the environment variable, `DEFAULT_SCHOLAR_FLUX_PROVIDER` is set to another provider.

        Args:
            query (str): The search keyword or query string.
            base_url (str): The base URL for the article API.
            records_per_page (int): Number of records to fetch per page (1-100).
            request_delay (Optional[float]): Minimum delay between requests in seconds.
            api_key (Optional[str | SecretStr]): API key if required.
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            user_agent (Optional[str]): Optional user-agent string for the session.
            use_cache (Optional[bool]): Indicates whether or not to use cache if a cached session doesn't yet exist.
            namespace (Optional[str]): Used for identifying batches of requests,
            masker (Optional[str]): Used for filtering potentially sensitive information from logs
            **api_specific_parameters: Additional api parameter-value pairs and overrides to be
                                            provided to SearchAPIConfig class
        Returns:
            A new SearchAPI instance initialized with the config chosen
        """
        try:
            default_provider_name = provider_name or config.get("DEFAULT_SCHOLAR_FLUX_PROVIDER", "PLOS")
            search_api_config = SearchAPIConfig.from_defaults(
                provider_name=default_provider_name, **api_specific_parameters
            )
        except (NotImplementedError, ValidationError) as e:
            raise APIParameterException(f"Invalid SearchAPIConfig: {e}") from e

        parameter_config = APIParameterConfig.from_defaults(default_provider_name)
        return cls.from_settings(
            query,
            config=search_api_config,
            parameter_config=parameter_config,
            session=session,
            timeout=timeout,
            user_agent=user_agent,
            use_cache=use_cache,
            masker=masker,
        )

    @staticmethod
    def is_cached_session(session: Union[CachedSession, requests.Session]) -> bool:
        """
        Checks whether the current session is a cached session. To do so,
        this method first determines whether the current object has a 'cache'
        attribute and whether the cache element, if existing, is a BaseCache

        Args:
            session (requests.Session): The session to check.

        Returns:
            bool: True if the session is a cached session, False otherwise.
        """
        cached_session = cast("CachedSession", session)
        return hasattr(cached_session, "cache") and isinstance(cached_session.cache, BaseCache)

    @property
    def cache(self) -> Optional[BaseCache]:
        """
        Retrieves the requests-session cache object if the session object
        is a CachedSession object. If a session cache does not exist, this
        function will return None

        Returns:
            Optional[BaseCache]: The cache object if available, otherwise None.
        """
        if not self.session:
            return None

        cached_session = cast("CachedSession", self.session)
        cache = getattr(cached_session, "cache", None)
        if isinstance(cache, BaseCache):
            return cache
        return None

    def build_parameters(
        self,
        page: int,
        additional_parameters: Optional[dict[str, Any]] = None,
        **api_specific_parameters,
    ) -> Dict[str, Any]:
        """
                Constructs the request parameters for the API call, using the provided APIParameterConfig and its
                associated APIParmaeterMap This method maps standard fields (query, page, records_per_page, api_key, etc.)
                to the provider-specific parameter names

                Using `additional_parameters`, an additional arbitrary set of parameter key-value can be added to request
                further customize or override parameter settings to the API. additional_parameters is offered as a convenience
                method in case an API may use additional arguments or a query requires specific advanced functionality.

                Other arguments and mappings can be supplied through **api_specific_parameters to the parameter config,
                provided that the options or pre-defined mappings exist in the config.

                Args:
                    page (int): The page number to request.
                    additional_parameters Optional[dict]: A dictionary of additional overrides not included in the original
                    **api_specific_parameters: Additional parameters to provide to the parameter config: Note that the config
                              will only accept keyword arguments that have been explicitly defined in the parameter map. For all
                              others, they must be added using the additional_parameters parameter
        .
                Returns:
                    Dict[str, Any]: The constructed request parameters.
        """
        # instanced parameters are generally static: thus page is the only parameter
        # Method to build request parameters

        api_specific_parameters = self.api_specific_parameters | api_specific_parameters
        parameters = self.parameter_config.build_parameters(
            query=self.query,
            page=page,
            records_per_page=self.records_per_page,
            api_key=self.api_key,
            **api_specific_parameters,
        )

        additional_parameters = self._validate_parameters(additional_parameters or {})

        filtered_parameters = {
            additional_parameter: values
            for additional_parameter, values in additional_parameters.items()
            if additional_parameter in parameters
            and values is not None
            and parameters.get(additional_parameter) is None
        }

        parameters.update(filtered_parameters)

        unknown_param_names = additional_parameters.keys() - parameters.keys()

        if unknown_param_names:
            logger.warning(
                f"The following parameters are not assicated with the current API config:" f"{unknown_param_names}"
            )

        unknown_parameters = {
            parameter: value for parameter, value in additional_parameters.items() if parameter in unknown_param_names
        }

        all_parameters = parameters | unknown_parameters

        return {k: v for k, v in all_parameters.items() if v is not None}

    def search(self, page: Optional[int] = None, parameters: Optional[Dict[str, Any]] = None) -> Response:
        """
        Public method to perform a search, by specifying either the page to query using the default parameters and
        additional overrides or by creating a custom request using a full dictionary containing the full set of
        parameters required.

        Args:
            page (Optional[int]): Page number to query. If provided, parameters are built from the config and this page.
            parameters (Optional[Dict[str, Any]]): If provided alone, used as the full parameter set for the request.
                     If provided together with `page`, these act as additional or overriding parameters on top of
                     the built config.

        Returns:
            A response object from the API containing articles and metadata


        """

        if page is None and parameters is not None:

            with self._rate_limiter.rate(self.config.request_delay):
                return self.send_request(self.base_url, parameters=parameters)

        elif page is not None:
            return self.make_request(page, parameters)
        else:
            raise APIParameterException("One of 'page' or 'parameters' must be provided")

    def make_request(self, current_page: int, additional_parameters: Optional[dict[str, Any]] = None) -> Response:
        """
        Constructs and sends a request to the chosen api:
            The parameters are built based on the default/chosen config and parameter map
        Args:
            page (int): The page number to request.
            additional_parameters Optional[dict]: A dictionary of additional overrides not included in the original
                                              SearchAPIConfig
        Returns:
            Response: The API's response to the request.
        """
        parameters = self.build_parameters(current_page, additional_parameters)

        with self._rate_limiter.rate(self.config.request_delay):
            response = self.send_request(self.base_url, parameters=parameters)

        return response

    def prepare_request(
        self,
        base_url: str,
        endpoint: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> requests.PreparedRequest:
        """
        Prepares a GET request for the specified endpoint with optional parameters.
        This method builds on the original base class method by additionally allowing
        users to specify a custom request directly while also accounting for the
        addition of an API key specific to the API.

        Args:
            base_url (str): The base URL for the API.
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            parameters (Optional[Dict[str, Any]]): Optional query parameters for the request.

        Returns:
            prepared_request (PreparedRequest) : The prepared request object.
        """
        try:
            # constructs the url with the endpoint
            url = urljoin(base_url, endpoint) if endpoint else base_url

            parameters = parameters or {}

            # attempt to retrieve the api key and parameter name if existing, else fallbck to api_key
            if api_key and not self._api_key_exists(parameters):
                api_key_parameter_name = self.parameter_config.parameter_map.api_key_parameter or "api_key"
                if api_key_parameter_name:
                    parameters[api_key_parameter_name] = api_key

            # registers patterns corresponding to data to clean from logs: note patterns are themselves
            # also stored as secrets for greater security
            cleaned_parameters = {}
            for parameter, value in parameters.items():
                self.masker.register_secret_if_exists(parameter, value)
                cleaned_parameters[parameter] = SecretUtils.unmask_secret(value)

            request = requests.Request("GET", url, params=cleaned_parameters)
            prepared_request = request.prepare()
            return prepared_request
        except Exception as e:
            raise RequestCreationException(
                "An unexpected error occurred:The request could"
                f"not be prepared for base_url={base_url}, "
                f"endpoint={endpoint}: {e}"
            )

    @staticmethod
    def _api_key_exists(parameters: Dict[str, Any]) -> bool:
        """
        Helper method for determining whether an api key exists in the
        list of dict parameters provided to the request

        Args:
            parameters (Dict): Optional query parameters for the request.

        Returns:
            bool: Indicates whether or not an api key parameter exists
        """
        for k in parameters:
            normalized = re.sub(rf"[{re.escape(punctuation)}]", "", k).lower()
            if normalized == "apikey":
                return True
        return False

    @contextmanager
    def with_config(
        self,
        config: Optional[SearchAPIConfig] = None,
        parameter_config: Optional[APIParameterConfig] = None,
        provider_name: Optional[str] = None,
    ) -> Iterator["SearchAPI"]:
        """
        Temporarily modifies the SearchAPI's SearchAPIConfig and/or APIParameterConfig and namespace.
        You can provide a config, a parameter_config, or a provider_name to fetch defaults.
        Explicitly provided configs take precedence over provider_name, and the context manager will revert
        changes to the parameter mappings and search configuration afterward.

        Args:
            config (Optional[SearchAPIConfig]): Temporary search api configuration to use within the context to control
                                                where and how response records are retrieved.
            parameter_config (Optional[APIParameterConfig]): Temporary parameter config to use within the context
                                                             to resolve universal parameters names to those that are
                                                             specific to the current api.
            provider_name (Optional[str]): used to retrieve the associated configuration for a specific provider
                                           in order to edit the parameter map when using a different provider.

        Yields:
            SearchAPI: The current api object with a temporarily swapped config during the context manager.
        """
        original_config = self.config
        original_parameter_config = self.parameter_config

        try:
            # Fetch from provider_name if needed
            if provider_name:
                provider_config = SearchAPIConfig.from_defaults(provider_name)
                provider_param_config = APIParameterConfig.from_defaults(provider_name)
            else:
                provider_config = None
                provider_param_config = None

            # Use explicit configs if provided, else fall back to provider_name
            self.config = config or provider_config or self.config
            self.parameter_config = parameter_config or provider_param_config or self.parameter_config

            yield self
        finally:
            self.config = original_config
            self.parameter_config = original_parameter_config

    @contextmanager
    def with_config_parameters(
        self, provider_name: Optional[str] = None, **api_specific_parameters
    ) -> Iterator[SearchAPI]:
        """
        Allows for the temporary modification of the search configuration, and parameter mappings,
        and cache namespace. for the current API. Uses a contextmanager to temporarily change the provided
        parameters without persisting the changes.

        Args:
            provider_name (Optional[str]): If provided, fetches the default parameter config for the provider.

            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override in the current config.

        Yields:
            SearchAPI: The API object with temporarily swapped config and/or parameter config.

        """

        original_search_config = self.config
        original_parameter_config = self.parameter_config

        try:
            if api_specific_parameters or provider_name:

                self.config = SearchAPIConfig.update(
                    current_config=self.config,
                    provider_name=provider_name,
                    **api_specific_parameters,
                )

            parameter_config = APIParameterConfig.get_defaults(provider_name) if provider_name else None

            if parameter_config:
                self.parameter_config = parameter_config

            yield self

        finally:
            self.config = original_search_config
            self.parameter_config = original_parameter_config

    def describe(self) -> dict:
        """
        A helper method used that describe accepted configuration for
        the current provider or user-defined parameter mappings.

        Returns:
            (dict): a dictionary describing valid config fields and provider-specific
                  api parameters for the current provider (if applicable).
        """
        config_fields = list(SearchAPIConfig.model_fields)
        provider_name = self.provider_name
        provider = provider_registry.get(provider_name)

        parameter_map = provider.parameter_map if provider else self.parameter_config.parameter_map

        return {
            "config_fields": config_fields,
            "api_specific_parameters": parameter_map.api_specific_parameters,
        }

    def __repr__(self) -> str:
        class_name = self.__class__.__name__

        attribute_dict = {
            "query": self.query,
            "config": repr(self.config),
            "session": self.session,
            "timeout": self.timeout,
        }

        return generate_repr_from_string(class_name, attribute_dict)


# if __name__ == '__main__':
#     import os
#     core_search_config=SearchAPIConfig.from_defaults('core')
#     core_search_config=SearchAPIConfig(base_url='https://api.core.ac.uk/v3/search/works',
#                                        records_per_page = 2,
#                                        request_delay=6)
#     api=SearchAPI.from_defaults(query='covariate shift',provider_name='core')
#     api.api_key
