# /api/search_api.py
"""Implements the SearchAPI that is the core interface used throughout the scholar_flux package to retrieve responses.

The SearchAPI builds on the BaseAPI to simplify parameter handling into a universal interface where the specifics of
parameter names and request formation are abstracted.

"""
from __future__ import annotations
from typing import Dict, Optional, Any, Annotated, Union, cast, Iterator
from contextlib import contextmanager
from requests_cache.backends.base import BaseCache
from requests_cache import CachedSession
from pydantic import SecretStr
import logging
import requests
from requests import Response
from scholar_flux import masker as default_masker
from scholar_flux.utils import config_settings
from scholar_flux.api.models import BaseAPIParameterMap
from scholar_flux.api import BaseAPI, APIParameterConfig, APIParameterMap, SearchAPIConfig, RateLimiter
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.models import ProviderConfig
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
    """The core interface that handles the retrieval of JSON, XML, and YAML content from the scholarly API sources
    offered by several providers such as SpringerNature, PLOS, and PubMed. The SearchAPI is structured to allow
    flexibility without complexity in initialization. API clients can be either constructed piece-by-piece or with
    sensible defaults for session-based retrieval, API key management, caching, and configuration options.

    This class is integrated into the SearchCoordinator as a core component of a pipeline that further
    parses the response, extracts records and metadata, and caches the processed records to facilitate downstream
    tasks such as research, summarization, and data mining.

    Examples:
        >>> from scholar_flux.api import SearchAPI
        # creating a basic API that uses the PLOS as the default while caching data in-memory:
        >>> api = SearchAPI(query = 'machine learning', provider_name = 'plos', use_cache = True)
        # retrieve a basic request:
        >>> response_page_1 = api.search(page = 1)
        >>> assert response_page_1.ok
        >>> response_page_1
        # OUTPUT: <Response [200]>
        >>> ml_page_1 = response_page_1.json()
        # future requests automatically wait until the specified request delay passes to send another request:
        >>> response_page_2 = api.search(page = 2)
        >>> assert response_page_1.ok
        >>> response_page_2
        # OUTPUT: <Response [200]
        >>> ml_page_2 = response_page_2.json()

    """

    DEFAULT_URL: str = "https://api.plos.org/search"
    DEFAULT_CACHED_SESSION: bool = False

    def __init__(
        self,
        query: str,
        provider_name: Optional[str] = None,
        parameter_config: Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig] = None,
        session: Optional[requests.Session | CachedSession] = None,
        user_agent: Optional[str] = None,
        timeout: Optional[int | float] = None,
        masker: Optional[SensitiveDataMasker] = None,
        use_cache: Optional[bool] = None,
        base_url: Optional[str] = None,  # SearchAPIConfig
        api_key: Optional[str | SecretStr] = None,  # SearchAPIConfig
        records_per_page: int = 20,  # SearchAPIConfig
        request_delay: Optional[float] = None,  # SearchAPIConfig
        **api_specific_parameters,  # SearchAPIConfig
    ):
        """Initializes the SearchAPI with a query and optional parameters. The absolute bare minimum for interacting
        with APIs requires a query, base_url, and an APIParameterConfig that associates relevant fields (aka query,
        records_per_page, etc. with fields that are specific to each API provider.

        Args:
            query (str):
                The search keyword or query string.
            provider_name (Optional[str]):
                The name of the API provider where requests will be sent. If a provider_name and base_url are both
                given, the SearchAPIConfig will prioritize base_urls over the provider_name.
            parameter_config (Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig]):
                A config that a parameter map attribute under the hood to build the parameters necessary to interact
                with an API. For convenience, an APIParameterMap can be provided in place of an APIParameterConfig,
                and the conversion will take place under the hood.
            session (Optional[requests.Session]):
                A pre-configured session or None to create a new session. A new session is created if not specified.
            user_agent (Optional[str]): Optional user-agent string for the session.
            timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError
            masker (Optional[str]):
                Used for filtering potentially sensitive information from logs (API keys, auth bearers, emails, etc)
            use_cache (bool):
                Indicates whether or not to create a cached session. If a cached session is already specified, this
                setting will have no effect on the creation of a session.
            base_url (str): The base URL for the article API.
            api_key (Optional[str | SecretStr]): API key if required.
            records_per_page (int): Number of records to fetch per page (1-100).
            request_delay (Optional[float]):
                Minimum delay between requests in seconds. If not specified, the SearchAPI, this setting will
                use the default request delay defined in the SearchAPIConfig (6.1 seconds) if an override for the
                current provider does not exist.
            **api_specific_parameters:
                Additional parameter-value pairs to be provided to SearchAPIConfig class. API specific parameters include:
                    mailto (Optional[str | SecretStr]): (CROSSREF: an optional contact for feedback on API usage)
                    db: str (PubMed: a database to retrieve data from (example: db=pubmed)

        """

        super().__init__(session=session, timeout=timeout, user_agent=user_agent, use_cache=use_cache)

        # Create SearchAPIConfig internally with defaults and validation
        try:

            # if neither the provider nor a base URL is provided, fall back to using the default URL
            if not base_url and not provider_name:
                base_url = self.DEFAULT_URL

            search_api_config = SearchAPIConfig(
                base_url=base_url or "",
                provider_name=provider_name or "",
                records_per_page=records_per_page,
                api_key=SecretUtils.mask_secret(api_key),
                request_delay=request_delay or -1,
                api_specific_parameters=api_specific_parameters,
            )

        except (NotImplementedError, ValidationError, APIParameterException) as e:
            raise APIParameterException(f"Invalid SearchAPIConfig: {e}") from e

        self._initialize(
            query,
            config=search_api_config,
            parameter_config=parameter_config,
            masker=masker,
        )

    def _initialize(
        self,
        query: str,
        config: SearchAPIConfig,
        parameter_config: Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig] = None,
        masker: Optional[SensitiveDataMasker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """Initializes the API session with the provided base URL and API key. This method is called during the
        initialization of the class.

        Args:
            query (str): The query to send to the current API provider. Note, this must be non-missing
            config (SearchAPIConfig): Configuration settings to used when sending requests to APIs.
            parameter_config (Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig]):
                Maps global scholar_flux parameters to those that are specific to the provider's API.
            masker (Optional[SensitiveDataMasker]):
                A masker used to filter logs of API keys and other sensitive data that may flow through the
                SearchAPI during parameter building and response retrieval.
            rate_limiter (Optional[RateLimiter]):
                An optional rate limiter to control the number of requests sent. When the request_delay and min_interval
                do not agree, `min_interval` is preferred.

        """
        self.config = config
        self.query = query
        self.last_request: Optional[float] = None
        self._rate_limiter: RateLimiter = rate_limiter or RateLimiter(min_interval=self.config.request_delay)
        self.masker: SensitiveDataMasker = masker or default_masker

        # prefer the rate limit derived from the RateLimiter if provided explicitly when neither matches
        if rate_limiter and self.config.request_delay != rate_limiter.min_interval:
            self.config.request_delay = config.default_request_delay(
                config.validate_request_delay(rate_limiter.min_interval), provider_name=self.config.provider_name
            )

        # first attempt to retrieve a non-empty parameter_config. If unsuccessful,
        # then whether the provided namespace or url matches a default provider

        parameter_config = APIParameterConfig.as_config(parameter_config) if parameter_config else None
        self.parameter_config = parameter_config or APIParameterConfig.from_defaults(self.provider_name)

        if self.parameter_config.map.api_key_required and not self.config.api_key:
            logger.warning("An API key is required but was not provided")
        logger.debug("Initialized a new SearchAPI Session Successfully.")

    @classmethod
    def update(
        cls,
        search_api: SearchAPI,
        query: Optional[str] = None,
        config: Optional[SearchAPIConfig] = None,
        parameter_config: Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig] = None,
        session: Optional[requests.Session | CachedSession] = None,
        user_agent: Optional[str] = None,
        timeout: Optional[int | float] = None,
        use_cache: Optional[bool] = None,
        masker: Optional[SensitiveDataMasker] = None,
        rate_limiter: Optional[RateLimiter] = None,
        **api_specific_parameters,
    ):
        """Helper method for generating a new SearchAPI from an existing SearchAPI instance. All parameters that are not
        modified are pulled from the original SearchAPI. If no changes are made, an identical SearchAPI is generated
        from the existing defaults.

        Args:
            config (SearchAPIConfig):
                Indicates the configuration settings to be used when sending requests to APIs
            parameter_config (Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig]):
                Maps global scholar_flux parameters to those that are API specific.
            session:(Optional[requests.Session | CachedSession]):
                An optional session to use for the creation of request sessions
            timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError
            use_cache: Optional[bool]: Indicates whether or not to use cache. The settings from session
                                       are otherwise used this option is not specified.
            masker: (Optional[SensitiveDataMasker]): A masker used to filter logs of API keys and other sensitive data
            user_agent: Optional[str] = An user agent to associate with the session


        Returns:
            SearchAPI: A newly constructed SearchAPI with the chosen/validated settings

        """
        if not isinstance(search_api, SearchAPI):
            raise APIParameterException(
                "Expected a SearchAPI to perform parameter updates. " f"Received type {type(search_api)}"
            )

        request_delay = api_specific_parameters.get("request_delay", getattr(rate_limiter, "min_interval", None))

        if request_delay is not None:
            api_specific_parameters["request_delay"] = request_delay

        config = (
            SearchAPIConfig.update(config or search_api.config, **api_specific_parameters)
            if config or api_specific_parameters
            else search_api.config
        )

        update_rate_limiter: Optional[RateLimiter] = rate_limiter or (
            search_api._rate_limiter if "request_delay" not in api_specific_parameters else None
        )

        if not parameter_config:
            parameter_config = (
                search_api.parameter_config if search_api.config.provider_name == config.provider_name else None
            )

        return SearchAPI.from_settings(
            query or search_api.query,
            config,
            parameter_config,
            session=session or search_api.session,
            timeout=timeout or search_api.timeout,
            use_cache=use_cache,
            masker=masker or search_api.masker,
            rate_limiter=update_rate_limiter,
            user_agent=user_agent,  # is pulled from the original API if not provided
        )

    @property
    def config(self) -> SearchAPIConfig:
        """Property method for accessing the config for the SearchAPI.

        Returns:
            The configuration corresponding to the API Provider

        """
        return self._config

    @config.setter
    def config(self, _config: SearchAPIConfig) -> None:
        """Used to ensure that assignments and updates to the SearchAPI configuration will work as intended. It first
        validates the configuration for the search api, and assigns the value if it is a SearchAPIConfig element.

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
        """Property method for accessing the parameter mapping config for the SearchAPI.

        Returns:
            The configuration corresponding to the API Provider

        """
        return self._parameter_config

    @parameter_config.setter
    def parameter_config(self, _parameter_config: BaseAPIParameterMap | APIParameterMap | APIParameterConfig) -> None:
        """Used to ensure that assignments and updates to the SearchAPI configuration will work as intended. It first
        validates the configuration for the search api, and assigns the value if it is an APIParameterConfig element.

        Args:
            _parameter_config (BaseAPIParameterMap | APIParameterMap | APIParameterConfig):
                The parameter mapping configuration to assign to the SearchAPI instance

        Raises:
            APIParameterException: Indicating that the provided value is not an APIParameterConfig

        """
        if not isinstance(_parameter_config, APIParameterConfig):
            raise APIParameterException(f"Expected an APIParameterConfig, received type: {type(_parameter_config)}")
        self._parameter_config = _parameter_config

    @property
    def provider_name(self) -> str:
        """Property method for accessing the provider name in the current SearchAPI instance.

        Returns:
            The name corresponding to the API Provider.

        """
        return self.config.provider_name

    @property
    def query(self) -> str:
        """Retrieves the current value of the query to be sent to the current API."""
        return self.__query

    @query.setter
    def query(self, query):
        """Uses the private method, __query to update the current query and uses validation to ensure that the query is
        a non-empty string."""
        if not query or not isinstance(query, str):
            raise QueryValidationException(f"Query must be a non empty string., received: {query}")
        self.__query = query

    @property
    def api_key(self) -> Optional[SecretStr]:
        """Retrieves the current value of the API key from the SearchAPIConfig as a SecretStr.

        Note that the API key is stored as a secret key when available. The value of the API key can be retrieved by
        using the `api_key.get_secret_value()` method.

        Returns:
            Optional[SecretStr]: A secret string of the API key if it exists

        """
        return self.config.api_key

    @property
    def base_url(self) -> str:
        """Corresponds to the base URL of the current API.

        Returns:
            The base URL corresponding to the API Provider

        """
        return self.config.base_url

    @property
    def records_per_page(self) -> int:
        """Indicates the total number of records to show on each page.

        Returns:
            int: an integer indicating the max number of records per page

        """
        return self.config.records_per_page

    @property
    def rate_limiter(self) -> RateLimiter:
        """Property enabling public access to the rate limiter for ease of use.

        Returns:
            RateLimiter: Throttles the number of requests that can sent to an API within a time interval.

        """
        return self._rate_limiter

    @property
    def request_delay(self) -> float:
        """Indicates how long we should wait in-between requests.

        Helpful for ensuring compliance with the rate-limiting requirements of various APIs.

        Returns:
            float: The number of seconds to wait at minimum between each request

        """
        return self.config.request_delay

    @property
    def api_specific_parameters(self) -> dict:
        """This property pulls additional parameters corresponding to the API from the configuration of the current API
        instance.

        Returns:
            dict[str, APISpecificParameter]: A list of all parameters specific to the current API.

        """
        return self.config.api_specific_parameters or {}

    @classmethod
    def from_settings(
        cls,
        query: str,
        config: SearchAPIConfig,
        parameter_config: Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig] = None,
        session: Optional[requests.Session | CachedSession] = None,
        user_agent: Optional[str] = None,
        timeout: Optional[int | float] = None,
        use_cache: Optional[bool] = None,
        masker=None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> SearchAPI:
        """Advanced constructor: instantiate directly from a SearchAPIConfig instance.

        Args:
            query (str): The search keyword or query string.
            config (SearchAPIConfig): Indicates the configuration settings to be used when sending requests to APIs
            parameter_config: (Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig]):
                Maps global scholar_flux parameters to those that are specific to the current API
            session:(Optional[requests.Session | CachedSession]):
                An optional session to use for the creation of request sessions
            timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError
            use_cache: Optional[bool]:
                Indicates whether or not to use cache. The settings from session are otherwise used this option is
                not specified.
            masker: (Optional[SensitiveDataMasker]): A masker used to filter logs of API keys and other sensitive data
            user_agent: Optional[str] = An user agent to associate with the session


        Returns:
            SearchAPI: A newly constructed SearchAPI with the chosen/validated settings

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
            query, config=config, parameter_config=parameter_config, masker=masker, rate_limiter=rate_limiter
        )
        return instance

    @classmethod
    def from_provider_config(
        cls,
        query: str,
        provider_config: ProviderConfig,
        session: Optional[requests.Session] = None,
        user_agent: Annotated[Optional[str], "An optional User-Agent to associate with each search"] = None,
        use_cache: Optional[bool] = None,
        timeout: Optional[int | float] = None,
        masker: Optional[SensitiveDataMasker] = None,
        rate_limiter: Optional[RateLimiter] = None,
        **api_specific_parameters,
    ) -> SearchAPI:
        """Factory method to create a new SearchAPI instance using a ProviderConfig.

        This method uses the default settings associated with the provider config to temporarily make the
        configuration settings globally available when creating the SearchAPIConfig and APIParameterConfig
        instances from the provider registry.

        Args:
            query (str): The search keyword or query string.
            provider_config: ProviderConfig,
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            user_agent (Optional[str]): Optional user-agent string for the session.
            use_cache (Optional[bool]): Indicates whether or not to use cache if a cached session doesn't yet exist.
            timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError.
            masker (Optional[str]): Used for filtering potentially sensitive information from logs
            **api_specific_parameters:
                Additional api parameter-value pairs and overrides to be provided to SearchAPIConfig class

        Returns:
            A new SearchAPI instance initialized with the chosen configuration.

        """
        provider_name = getattr(provider_config, "provider_name", "")
        original_provider_config = provider_registry.get(provider_name)

        try:
            provider_registry.add(provider_config)  # raises an error if the current object is not a provider config

            search_api_config = SearchAPIConfig.from_defaults(provider_name=provider_name, **api_specific_parameters)

            parameter_config = APIParameterConfig.from_defaults(provider_name)

            return cls.from_settings(
                query,
                config=search_api_config,
                parameter_config=parameter_config,
                session=session,
                timeout=timeout,
                user_agent=user_agent,
                use_cache=use_cache,
                masker=masker,
                rate_limiter=rate_limiter,
            )

        except (TypeError, AttributeError, NotImplementedError, ValidationError, APIParameterException) as e:
            msg = f"The SearchAPI could not be created with the provided configuration: {e}"
            logger.error(msg)
            raise APIParameterException(msg) from e

        finally:
            if original_provider_config:
                # replaces the temporary configuration with the original configuration if there is an original
                provider_registry[provider_name] = original_provider_config

            elif provider_name in provider_registry:
                # otherwise removes the temporary configuration
                provider_registry.remove(provider_name)

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
        rate_limiter: Optional[RateLimiter] = None,
        **api_specific_parameters,
    ) -> SearchAPI:
        """Factory method to create SearchAPI instances with sensible defaults for known providers.

        PLOS is used by default unless the environment variable, `SCHOLAR_FLUX_DEFAULT_PROVIDER` is set to
        another provider.

        Args:
            query (str): The search keyword or query string.
            base_url (str): The base URL for the article API.
            records_per_page (int): Number of records to fetch per page (1-100).
            request_delay (Optional[float]): Minimum delay between requests in seconds.
            api_key (Optional[str | SecretStr]): API key if required.
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            user_agent (Optional[str]): Optional user-agent string for the session.
            use_cache (Optional[bool]): Indicates whether or not to use cache if a cached session doesn't yet exist.
            masker (Optional[str]): Used for filtering potentially sensitive information from logs
            **api_specific_parameters:
                Additional api parameter-value pairs and overrides to be provided to SearchAPIConfig class
        Returns:
            A new SearchAPI instance initialized with the config chosen.

        """
        try:
            default_provider_name = provider_name or config_settings.get("SCHOLAR_FLUX_DEFAULT_PROVIDER", "PLOS")
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
            rate_limiter=rate_limiter,
        )

    @staticmethod
    def is_cached_session(session: Union[CachedSession, requests.Session]) -> bool:
        """Checks whether the current session is a cached session.

        To do so, this method first determines whether the current object has a 'cache' attribute and whether the cache
        element, if existing, is a BaseCache.

        Args:
            session (requests.Session): The session to check.

        Returns:
            bool: True if the session is a cached session, False otherwise.

        """
        cached_session = cast("CachedSession", session)
        return hasattr(cached_session, "cache") and isinstance(cached_session.cache, BaseCache)

    @property
    def cache(self) -> Optional[BaseCache]:
        """Retrieves the requests-session cache object if the session object is a `CachedSession` object.

        If a session cache does not exist, this function will return None.

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
        """Constructs the request parameters for the API call, using the provided APIParameterConfig and its associated
        APIParameterMap. This method maps standard fields (query, page, records_per_page, api_key, etc.) to the
        provider-specific parameter names.

        Using `additional_parameters`, an arbitrary set of parameter key-value can be added to request further
        customize or override parameter settings to the API. additional_parameters is offered as a convenience
        method in case an API may use additional arguments or a query requires specific advanced functionality.

        Other arguments and mappings can be supplied through `**api_specific_parameters` to the parameter config,
        provided that the options or pre-defined mappings exist in the config.

        When `**api_specific_parameters` and `additional_parameters` conflict, additional_parameters is considered
        the ground truth. If any remaining parameters are `None` in the constructed list of parameters, these
        values will be dropped from the final dictionary.

        Args:
            page (int): The page number to request.
            additional_parameters Optional[dict]:
                A dictionary of additional overrides that may or may not have been included in the original parameter
                map of the current API. (Provided for further customization of requests).
            **api_specific_parameters:
                Additional parameters to provide to the parameter config: Note that the
                config will only accept keyword arguments that have been explicitly
                defined in the parameter map. For all others, they must be added using
                the additional_parameters parameter.

        Returns:
            Dict[str, Any]: The constructed request parameters.

        """

        # validate the complete list of additional parameter overrides if provided
        additional_parameters = self._validate_parameters(additional_parameters or {})

        # contains the full list of all parameters specific to the current API
        all_parameter_names = set(self.parameter_config.show_parameters())

        # Method to build request parameters from the original parameter map
        api_specific_parameters = self.api_specific_parameters | api_specific_parameters

        # Identify all parameters found in the list of additional_parameters that are also specific to the current API
        api_specific_parameters |= {
            parameter_name: additional_parameters.pop(parameter_name, None)
            for parameter_name in all_parameter_names
            if parameter_name in additional_parameters
        }

        # removing and retrieving the API key from additional_parameters if otherwise not provided.
        # on conflicts where an api key is provided twice, this will raise an error instead
        api_key = (
            self.api_key
            or api_specific_parameters.pop("api_key", None)
            or api_specific_parameters.pop(self.parameter_config.map.api_key_parameter or "", None)
        )

        if api_key is not None and self.api_key is None:
            logger.warning(
                "Note that, while dynamic changes to a missing API key is possible in request building, "
                "is not encouraged. Instead, redefine the `api_key` parameter as an "
                "attribute in the current SearchAPI."
            )

        # parameters that are duplicated can result in inconsistencies down the line - raise an error first
        duplicated_parameters = self.parameter_config._find_duplicated_parameters(api_specific_parameters)

        if duplicated_parameters:
            raise APIParameterException(
                "Attempted to override core parameters (query, records_per_page, api_key) via api_specific_parameters. "
                "This is not allowed. Please set these values via the SearchAPI constructor or attributes or use"
                "the `with_config` context manager instead."
            )

        # log when api specific parameter overrides are applied
        if api_specific_parameters:
            logger.debug(
                "The following additional parameters will be used to override the current parameter list:"
                f" {api_specific_parameters}"
            )

        # Builds the final set of parameters-value mappings from the API specific parameter list
        parameters = self.parameter_config.build_parameters(
            query=self.query,
            page=page,
            records_per_page=self.records_per_page,
            api_key=api_key,
            **api_specific_parameters,
        )

        # all remaining parameters not found in the list of `all_parameter_names` are then unknown.
        # log a warning before applying these in case this is not the user's intention
        if additional_parameters:
            logger.warning(
                f"The following additional parameters are not associated with the current API config:"
                f" {additional_parameters}"
            )

        # adds these remaining unknown parameters to the dictionary of current parameter-value mappings
        all_parameters = parameters | additional_parameters

        # note that some parameters above can be None. These parameters are removed prior to returning the dictionary
        return {parameter: value for parameter, value in all_parameters.items() if value is not None}

    def search(
        self,
        page: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        request_delay: Optional[float] = None,
        endpoint: Optional[str] = None,
    ) -> Response:
        """Public method to perform a search for the selected page with the current API configuration.

        A search can be performed by specifying either the page to query with the preselected defaults and additional
        parameter overrides for other parameters accepted by the API.

        Users can also create a custom request using a parameter dictionary containing the full set of API parameters.

        Args:
            page (Optional[int]): Page number to query. If provided, parameters are built from the config and this page.
            parameters (Optional[Dict[str, Any]]):
                If provided alone, used as the full parameter set for the request.
                If provided together with `page`, these act as additional or overriding parameters on top of
                the built config.
            request_delay (Optional[float]): Overrides the configured request delay for the current request only.
            endpoint (Optional[str]): An Optional API endpoint to append to base_url.

        Returns:
            requests.Response: A response object from the API containing articles and metadata

        """

        if page is None and (parameters is not None or endpoint is not None):

            with self.rate_limiter.rate(self.config.request_delay if request_delay is None else request_delay):
                return self.send_request(self.base_url, endpoint=endpoint, parameters=parameters)

        elif page is not None:
            return self.make_request(page, parameters, request_delay=request_delay, endpoint=endpoint)
        else:
            raise APIParameterException("One of 'page' or 'parameters' must be provided")

    def prepare_search(
        self,
        page: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        request_delay: Optional[float] = None,
        endpoint: Optional[str] = None,
    ) -> requests.PreparedRequest:
        """Prepares the current request given the provided page and parameters.

        The prepared request object can be sent using the `SearchAPI.session.send` method with `requests.Session` and
        `requests_cache.CachedSession`objects.

        Args:
            page (Optional[int]): Page number to query. If provided, parameters are built from the config and this page.
            parameters (Optional[Dict[str, Any]]):
                If provided alone, used as the full parameter set to build the current request.
                If provided together with `page`, these act as additional or overriding parameters on top of
                the built config.
            request_delay (Optional[float]):
                No-Op: retained to emulate the `.search()` method's parameters to ensure that the value is not included
                in the request parameters.
            endpoint (Optional[str]): The API endpoint to prepare the request for.

        Returns:
            requests.PreparedRequest:
                A request object that can be sent via `api.session.send`.

        """

        parameters = (
            {k: v for k, v in parameters.items() if k != "request_delay"}
            if isinstance(parameters, dict)
            else parameters
        )

        if page is None and parameters is not None or endpoint is not None:
            return self.prepare_request(self.base_url, endpoint=endpoint, parameters=parameters)
        elif page is not None:
            parameters = self.build_parameters(page, additional_parameters=parameters)
            return self.prepare_request(self.base_url, endpoint=endpoint, parameters=parameters)
        else:
            raise APIParameterException("One of 'page' or 'parameters' must be provided")

    def make_request(
        self,
        current_page: int,
        additional_parameters: Optional[dict[str, Any]] = None,
        request_delay: Optional[float] = None,
        endpoint: Optional[str] = None,
    ) -> Response:
        """Constructs and sends a request to the chosen api:

        The parameters are built based on the default/chosen config and parameter map
        Args:
            page (int): The page number to request.
            additional_parameters Optional[dict]:
                A dictionary of additional overrides not included in the original SearchAPIConfig
            request_delay (Optional[float]): Overrides the configured request delay for the current request only.
            endpoint (Optional[str]): The API endpoint to prepare the request for.
        Returns:
            requests.Response: The API's response to the request.

        """

        parameters = self.build_parameters(current_page, additional_parameters=additional_parameters)

        with self.rate_limiter.rate(self.config.request_delay if request_delay is None else request_delay):
            response = self.send_request(self.base_url, endpoint=endpoint, parameters=parameters)

        return response

    def prepare_request(
        self,
        base_url: Optional[str] = None,
        endpoint: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> requests.PreparedRequest:
        """Prepares a GET request for the specified endpoint with optional parameters.

        This method builds on the
        original base class method by additionally allowing users to specify a custom request directly while also
        accounting for the addition of an API key specific to the API.

        Args:
            base_url (str): The base URL for the API.
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            parameters (Optional[Dict[str, Any]]): Optional query parameters for the request.

        Returns:
            requests.PreparedRequest: The prepared request object.

        """
        current_base_url = base_url or self.base_url
        try:
            # constructs the url with the endpoint

            url = urljoin(current_base_url, endpoint) if endpoint else current_base_url

            parameters = self._validate_parameters(parameters or {})

            # attempt to retrieve the api key and parameter name if existing, else fallback to api_key
            if api_key and not self._api_key_exists(parameters):
                api_key_parameter_name = self.parameter_config.map.api_key_parameter or "api_key"
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
                "An unexpected error occurred: The request could "
                f"not be prepared for base_url={current_base_url}, "
                f"endpoint={endpoint}: {e}"
            )

    @staticmethod
    def _api_key_exists(parameters: Dict[str, Any]) -> bool:
        """Helper method for determining whether an api key exists in the list of dict parameters provided to the
        request.

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
        query: Optional[str] = None,
    ) -> Iterator[SearchAPI]:
        """Temporarily modifies the SearchAPI's SearchAPIConfig and/or APIParameterConfig and namespace. You can provide
        a config, a parameter_config, or a provider_name to fetch defaults. Explicitly provided configs take precedence
        over provider_name, and the context manager will revert changes to the parameter mappings and search
        configuration afterward.

        Args:
            config (Optional[SearchAPIConfig]):
                Temporary search api configuration to use within the context to control where and how response records
                are retrieved.
            parameter_config (Optional[APIParameterConfig]):
                Temporary parameter config to use within the context to resolve universal parameters names to those that
                are specific to the current api.
            provider_name (Optional[str]):
                Used to retrieve the associated configuration for a specific provider in order to edit the parameter map
                when using a different provider.
            query (Optional[str]):
                Allows users to temporarily modify the query used to retrieve records from an API.

        Yields:
            SearchAPI: The current api object with a temporarily swapped config during the context manager.

        """
        original_config = self.config
        original_parameter_config = self.parameter_config
        original_query = self.query

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
            parameter_config = APIParameterConfig.as_config(parameter_config) if parameter_config else None
            self.parameter_config = parameter_config or provider_param_config or self.parameter_config
            self.query = query or self.query

            yield self
        finally:
            self.config = original_config
            self.parameter_config = original_parameter_config
            self.query = original_query

    @contextmanager
    def with_config_parameters(
        self, provider_name: Optional[str] = None, query: Optional[str] = None, **api_specific_parameters
    ) -> Iterator[SearchAPI]:
        """Allows for the temporary modification of the search configuration, and parameter mappings, and cache
        namespace. For the current API. Uses a `contextmanager` to temporarily change the provided parameters without
        persisting the changes.

        Args:
            provider_name (Optional[str]): If provided, fetches the default parameter config for the provider.
            query (Optional[str]): Allows users to temporarily modify the query used to retrieve records from an API.
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override in the current config.

        Yields:
            SearchAPI: The API object with temporarily swapped config and/or parameter config.

        """

        original_search_config = self.config
        original_parameter_config = self.parameter_config
        original_query = self.query

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

            self.query = query or self.query

            yield self

        finally:
            self.config = original_search_config
            self.parameter_config = original_parameter_config
            self.query = original_query

    def describe(self) -> dict:
        """A helper method used that describe accepted configuration for the current provider or user-defined parameter
        mappings.

        Returns:
            dict:
                a dictionary describing valid config fields and provider-specific api parameters for the current provider
                (if applicable).

        """
        config_fields = list(SearchAPIConfig.model_fields)
        provider_name = self.provider_name
        provider = provider_registry.get(provider_name)

        parameter_map = provider.parameter_map if provider else self.parameter_config.map

        return {
            "config_fields": config_fields,
            "api_specific_parameters": parameter_map.api_specific_parameters,
        }

    def summary(self) -> str:
        """Create a summary representation of the current structure of the API."""
        class_name = self.__class__.__name__

        attribute_dict = {
            "query": self.query,
            "provider_name": self.provider_name,
            "base_url": self.base_url,
            "records_per_page": self.records_per_page,
            "api_key": "***" if self.config.api_key else None,
            "session": self.session.__class__.__name__ + "(...)",
            "timeout": self.timeout,
        }

        return generate_repr_from_string(class_name, attribute_dict, flatten=True)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for quickly showing a representation of the overall structure of the SearchAPI. The helper
        function, generate_repr_from_string helps produce human-readable representations of the core structure of the
        SearchAPI.

        Args:
            flatten (bool): Whether to flatten the SearchAPI's structural representation into a single line.
            show_value_attributes (bool): Whether to show nested attributes of the components of the SearchAPI.

        Returns:
            str: The structure of the current SearchAPI as a string.

        """

        class_name = self.__class__.__name__

        attribute_dict = {
            "query": self.query,
            "config": repr(self.config),
            "session": self.session,
            "timeout": self.timeout,
        }

        return generate_repr_from_string(
            class_name, attribute_dict, flatten=flatten, show_value_attributes=show_value_attributes
        )


__all__ = ["SearchAPI"]
