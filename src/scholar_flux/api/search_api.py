# /api/search_api.py
"""Implements the SearchAPI that is the core interface used throughout the scholar_flux package to retrieve responses.

The SearchAPI builds on the BaseAPI to simplify parameter handling into a universal interface where the specifics of
parameter names and request formation are abstracted.

"""

from __future__ import annotations
from typing import Optional, Any, Annotated, Iterator, cast
from contextlib import contextmanager
from requests.auth import AuthBase
from requests_cache.session import CachedSession
from pydantic import SecretStr
import logging
import requests
from requests import Response
from scholar_flux import masker as default_masker
from scholar_flux.utils import config_settings
from scholar_flux.api.models import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api import BaseAPI, APIParameterConfig, APIParameterMap, SearchAPIConfig, RateLimiter
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.models import ProviderConfig
from scholar_flux.sessions.auth import AuthAPIKeyBase, AuthAPIKeyHeader, AuthAPIKeyParameter
from scholar_flux.exceptions.api_exceptions import (
    APIParameterException,
    QueryValidationException,
    RequestCreationException,
)
from scholar_flux.security import SensitiveDataMasker, SecretUtils
from scholar_flux.utils.repr_utils import generate_repr_from_string
from scholar_flux.utils.settings_utils import SettingsDict, SettingsDictType
from pydantic import ValidationError
import re
from urllib.parse import urljoin
from string import punctuation

logger = logging.getLogger(__name__)


class SearchAPI(BaseAPI):
    """Core API interface that handles the retrieval of JSON, XML, and YAML content from the scholarly API sources.

    The `SearchAPI` supports record retrieval from several APIs offered by providers such as Springer Nature, PLOS,
    and PubMed. The SearchAPI is structured to allow flexibility without complexity in initialization. API clients
    can be either constructed piece-by-piece or with sensible defaults for session-based retrieval, API key management,
    caching, and configuration options.

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

    def __init__(
        self,
        query: str,
        provider_name: Optional[str] = None,
        parameter_config: Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig] = None,
        session: Optional[requests.Session | CachedSession] = None,
        *,
        user_agent: Optional[str] = None,
        timeout: Optional[int | float] = None,
        masker: Optional[SensitiveDataMasker] = None,
        use_cache: Optional[bool] = None,
        base_url: Optional[str] = None,  # SearchAPIConfig
        api_key: Optional[str | SecretStr] = None,  # SearchAPIConfig
        records_per_page: int = 20,  # SearchAPIConfig
        request_delay: Optional[float] = None,  # SearchAPIConfig
        **api_specific_parameters: Any,  # SearchAPIConfig
    ) -> None:
        """Initializes the SearchAPI with a query and optional parameters.

        The absolute bare minimum for interacting with APIs requires a query, base_url, and an APIParameterConfig that associates relevant fields (aka query,
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
                api_key=SecretUtils.mask_secret(api_key, convert_object=False),
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
        *,
        masker: Optional[SensitiveDataMasker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        """Initializes the API session with the provided base URL and API key.

        This method is called during the initialization of the class.

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
        *,
        user_agent: Optional[str] = None,
        timeout: Optional[int | float] = None,
        use_cache: Optional[bool] = None,
        masker: Optional[SensitiveDataMasker] = None,
        rate_limiter: Optional[RateLimiter] = None,
        **api_specific_parameters: Any,
    ) -> SearchAPI:
        """Helper method for generating a new SearchAPI from an existing SearchAPI instance.

        All parameters that are not modified are pulled from the original SearchAPI. If no changes are made, an identical SearchAPI is generated
        from the existing defaults.

        Args:
            search_api (Optional[SearchAPI]):
                The SearchAPI to be updated.
            query (str): The search keyword or query string.
            config (SearchAPIConfig):
                Indicates the configuration settings to be used when sending requests to APIs
            parameter_config (Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig]):
                Maps global scholar_flux parameters to those that are API specific.
            session:(Optional[requests.Session | CachedSession]):
                An optional session to use for the creation of request sessions
            user_agent (Optional[str]): A user agent to associate with the session
            timeout: (Optional[int | float]): Identifies the number of seconds to wait before raising a TimeoutError
            use_cache: Optional[bool]: Indicates whether or not to use cache. The settings from session
                                       are otherwise used this option is not specified.
            masker: (Optional[SensitiveDataMasker]): A masker used to filter logs of API keys and other sensitive data
            rate_limiter (Optional[RateLimiter]):
                A configured rate limiter for enforcing a minimum request delay.
            **api_specific_parameters:
                Additional api parameter-value pairs and overrides to be provided to SearchAPIConfig class.

        Returns:
            SearchAPI: A newly constructed SearchAPI with the chosen/validated settings

        """
        if not isinstance(search_api, SearchAPI):
            raise APIParameterException(
                f"Expected a SearchAPI to perform parameter updates. Received type {type(search_api)}"
            )

        request_delay = api_specific_parameters.get("request_delay", getattr(rate_limiter, "min_interval", None))

        if request_delay is not None:
            api_specific_parameters["request_delay"] = request_delay

        config = (
            SearchAPIConfig.update(config or search_api.config, **api_specific_parameters)
            if config or api_specific_parameters
            else search_api.config
        )

        # Reuse the existing RateLimiter for the same host if neither a new RateLimiter nor request_delay are provided.
        # This prevents both unnecessary delays between requests and `Too Many Requests` errors.
        update_rate_limiter: Optional[RateLimiter] = rate_limiter or (
            search_api.rate_limiter
            if config.url_basename == search_api.config.url_basename and "request_delay" not in api_specific_parameters
            else None
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
        """Used to ensure that assignments and updates to the `SearchAPI` configuration will work as intended.

        It first validates the configuration for the search api, and assigns the value if it is a SearchAPIConfig element.

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
        """Validates and assigns a valid `APIParameterConfig` to the current `SearchAPI`.

        When an `APIParameterMap` or `BaseAPIParameterMap` is received, it is converted under the hood via
        `APIParameterConfig.as_config()`. For all other types, an error is raised.

        Args:
            _parameter_config (BaseAPIParameterMap | APIParameterMap | APIParameterConfig):
                The parameter mapping configuration to assign to the SearchAPI instance

        Raises:
            APIParameterException: Indicating that the provided value is not an APIParameterConfig

        """
        if not isinstance(_parameter_config, (BaseAPIParameterMap, APIParameterMap, APIParameterConfig)):
            raise APIParameterException(f"Expected an APIParameterConfig, received type: {type(_parameter_config)}")
        self._parameter_config = APIParameterConfig.as_config(_parameter_config)

    @property
    def provider_name(self) -> str:
        """Property method for accessing the provider name in the current SearchAPI instance.

        Returns:
            The name corresponding to the API Provider.

        """
        return self.config.provider_name

    @property
    def display_name(self) -> str:
        """Human-readable provider name for logging and display purposes."""
        return provider_registry.get_display_name(self.provider_name) or self.provider_name

    @property
    def query(self) -> str:
        """Retrieves the current value of the query to be sent to the current API."""
        return self.__query

    @query.setter
    def query(self, query: str) -> None:
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
    def api_specific_parameters(self) -> dict[str, APISpecificParameter]:
        """This property pulls additional parameters corresponding to the API from the configuration of the current API
        instance.

        Returns:
            dict[str, APISpecificParameter]: A dictionary of all parameters specific to the current API.

        """
        return self.config.api_specific_parameters or {}

    @classmethod
    def from_settings(
        cls,
        query: str,
        config: SearchAPIConfig,
        parameter_config: Optional[BaseAPIParameterMap | APIParameterMap | APIParameterConfig] = None,
        session: Optional[requests.Session | CachedSession] = None,
        *,
        user_agent: Optional[str] = None,
        timeout: Optional[int | float] = None,
        use_cache: Optional[bool] = None,
        masker: Optional[SensitiveDataMasker] = None,
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
            user_agent (Optional[str]): A user agent to associate with the session.
            use_cache: Optional[bool]:
                Indicates whether or not to use cache. The settings from session are otherwise used this option is
                not specified.
            masker (Optional[SensitiveDataMasker]): A masker used to filter logs of API keys and other sensitive data.

        Returns:
            SearchAPI: A newly constructed SearchAPI with the chosen/validated settings.

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
        *,
        user_agent: Annotated[Optional[str], "An optional User-Agent to associate with each search"] = None,
        use_cache: Optional[bool] = None,
        timeout: Optional[int | float] = None,
        masker: Optional[SensitiveDataMasker] = None,
        rate_limiter: Optional[RateLimiter] = None,
        **api_specific_parameters: Any,
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
                Additional api parameter-value pairs and overrides to be provided to SearchAPIConfig class.

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
    def get_default_provider_name(cls) -> str:
        """Retrieves the name of the default provider as configured via `config_settings`.

        Note:
            When `config_settings` does not resolve to a known provider, a warning is raised, and
            SearchAPIConfig.DEFAULT_PROVIDER is returned instead.

        Returns:
            str:
                A known default, either resolved from `SCHOLAR_FLUX_DEFAULT_PROVIDER` or
                `SearchAPIConfig.DEFAULT_PROVIDER`.

        """
        default_provider_name = config_settings.get("SCHOLAR_FLUX_DEFAULT_PROVIDER")
        default_provider_config = provider_registry.get(default_provider_name)
        if default_provider_name is not None and not default_provider_config:
            logger.warning(
                f"The provider name, '{default_provider_name}' configured from the environment variable, "
                "SCHOLAR_FLUX_DEFAULT_PROVIDER, does not reference a valid provider. "
                f"Defaulting to the provider, {SearchAPIConfig.DEFAULT_PROVIDER} instead..."
            )
        return default_provider_config.provider_name if default_provider_config else SearchAPIConfig.DEFAULT_PROVIDER

    @classmethod
    def from_defaults(
        cls,
        query: str,
        provider_name: Optional[str],
        session: Optional[requests.Session] = None,
        *,
        user_agent: Annotated[Optional[str], "An optional User-Agent to associate with each search"] = None,
        use_cache: Optional[bool] = None,
        timeout: Optional[int | float] = None,
        masker: Optional[SensitiveDataMasker] = None,
        rate_limiter: Optional[RateLimiter] = None,
        **api_specific_parameters: Any,
    ) -> SearchAPI:
        """Factory method to create SearchAPI instances with sensible defaults for known providers.

        PLOS is used by default unless the environment variable, `SCHOLAR_FLUX_DEFAULT_PROVIDER` is set to
        another provider.

        Args:
            query (str): The search keyword or query string.
            provider_name (Optional[str]):
                The provider configuration to retrieve and use to initialize the `SearchAPI`.
            session (Optional[requests.Session]): A pre-configured session or None to create a new session.
            user_agent (Optional[str]): Optional user-agent string for the session.
            use_cache (Optional[bool]): Indicates whether or not to use cache if a cached session doesn't yet exist.
            timeout (Optional[int |float]): The total number of seconds to wait before raising a TimeoutError.
            masker (Optional[str]): Used for filtering potentially sensitive information from logs
            rate_limiter (Optional[RateLimiter]): A configured rate limiter for enforcing a minimum request delay.
            **api_specific_parameters:
                Additional api parameter-value pairs and overrides to be provided to SearchAPIConfig class.

        Returns:
            A new SearchAPI instance initialized with the config chosen.

        """
        try:
            default_provider_name = provider_name or cls.get_default_provider_name()
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

    def build_auth(
        self,
        parameters: Optional[SettingsDictType] = None,
        *,
        auth: Optional[AuthBase] = None,
        parameter_name: Optional[str] = None,
        scheme: Optional[str] = None,
        **api_specific_parameters: Any,
    ) -> Optional[AuthBase | AuthAPIKeyParameter | AuthAPIKeyHeader]:
        """Optionally returns an Authorization subclass enabling customizable authorization hooks.

        Note: When passing a `parameters` dictionary directly, API key fields are removed if they exist to avoid
        downstream duplication of API keys in headers and/or URL queries. To retain the `parameters` dictionary as is,
        unpack it instead (i.e., `api.build_auth(**parameters)`).

        Args:
            parameters (Optional[dict[str, Any] | SettingsDict]):
                An optional dictionary to extract API key fields from.
            auth (Optional[AuthBase]): An authorization hook onto the request. If available, it is returned as is.
            parameter_name (Optional[str]): The name of the API key parameter to be transmitted via dict or headers.
            scheme (Optional[str]): Scheme that prefixes the api key in the request header (i.e., `Bearer [API_KEY]`).
            **api_specific_parameters: keyword parameters to extract the API key from.

        Returns:
            Optional[AuthBase | AuthAPIKeyParameter | AuthAPIKeyHeader]:
                The newly initialized authorization hook when an API key or token is available via `self.config.api_key`
                or from a field extracted from `parameters` or `**api_specific_parameters`.

        """
        try:
            # Should remove both API key parameters if any one of them still exists. Keys should only exist in auth.
            extracted_api_key = self.parameter_config.extract_api_key(parameters, **api_specific_parameters)

            if auth is not None:
                return auth

            api_key = extracted_api_key if extracted_api_key else self.api_key

            use_auth = bool(api_key) or self.parameter_config.map.api_key_required
            # Note: NoneTyped API keys will be identified on validation and raise the appropriate error.
            if self.parameter_config.map.api_key_in_headers and use_auth:
                auth = AuthAPIKeyHeader(
                    api_key=cast("str | SecretStr", api_key),
                    scheme=scheme or self.parameter_config.map.api_key_scheme,
                    parameter_name=parameter_name or self.parameter_config.map.api_key_parameter,
                )
            elif not self.parameter_config.map.api_key_in_headers and use_auth:
                auth = AuthAPIKeyParameter(
                    api_key=cast("str | SecretStr", api_key),
                    parameter_name=parameter_name or self.parameter_config.map.api_key_parameter,
                )
            return auth
        except APIParameterException as e:
            error_type = e.__class__
            err = f"SearchAPI auth initialization failed: {e}"
            logger.error(err)
            raise error_type(err) from e  # Further annotates auth-related errors for observability

    def build_parameters(
        self,
        page: int,
        additional_parameters: Optional[SettingsDictType] = None,
        *,
        include_api_key: bool | None = None,
        **api_specific_parameters: Any,
    ) -> SettingsDictType:
        """Constructs the `params` dict for the request to be sent to the API based on the current page and config.

        This method builds the request parameter dictionary by referencing the API's `SearchAPIConfig`, the
        provider-specific `APIParameterConfig`, and its associated parameter mappings. The underlying `APIParameterMap`
        resolves universal fields (query, page, records_per_page, api_key, etc.) to provider-specific parameter names
        before constructing the request parameter dictionary.

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
            additional_parameters Optional[dict[str, Any] | SettingsDict]:
                A dictionary of additional overrides that may or may not have been included in the original parameter
                map of the current API. (Provided for further customization of requests).
            include_api_key (bool | None):
                Indicates whether an API key should be included. If `None`, an API key is added when required.
            **api_specific_parameters:
                Additional parameters to provide to the parameter config: Note that the
                config will only accept keyword arguments that have been explicitly
                defined in the parameter map. For all others, they must be added using
                the additional_parameters parameter.

        Returns:
            dict[str, Any] | SettingsDict: The constructed request parameters.

        """
        # validate the complete list of additional parameter overrides if provided
        additional_parameters = self._validate_parameters(additional_parameters or {}).copy()

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

        # log when API-specific parameter overrides are applied
        if api_specific_parameters:
            logger.debug(
                "The following additional parameters will be used to override the current parameter list for "
                f"{self.display_name}: {api_specific_parameters}"
            )

        # Builds the final set of parameters-value mappings from the API specific parameter list
        parameters = self.parameter_config.build_parameters(
            query=self.query,
            page=page,
            records_per_page=self.records_per_page,
            api_key=api_key,
            include_api_key=include_api_key,
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
        prepared_parameters = {parameter: value for parameter, value in all_parameters.items() if value is not None}
        return (
            SettingsDict(prepared_parameters)
            if isinstance(additional_parameters, SettingsDict)
            else prepared_parameters
        )

    def search(
        self,
        page: Optional[int] = None,
        parameters: Optional[dict[str, Any]] = None,
        endpoint: Optional[str] = None,
        *,
        request_delay: Optional[float] = None,
        auth: Optional[AuthBase] = None,
    ) -> Response:
        """Public method to perform a search for the selected page with the current API configuration.

        A search can be performed by specifying either the page to query with the preselected defaults and additional
        parameter overrides for other parameters accepted by the API.

        Users can also create a custom request using a parameter dictionary containing the full set of API parameters.

        Args:
            page (Optional[int]): Page number to query. If provided, parameters are built from the config and this page.
            parameters (Optional[dict[str, Any]]):
                If provided alone, used as the full parameter set for the request.
                If provided together with `page`, these act as additional or overriding parameters on top of
                the built config.
            endpoint (Optional[str]): An Optional API endpoint to append to base_url.
            request_delay (Optional[float]): Overrides the configured request delay for the current request only.
            auth (Optional[AuthBase]):
                An AuthBase subclass (i.e., AuthAPIKeyParameter, AuthAPIKeyHeader). When provided, this parameter
                controls how authentication with API keys or tokens is performed.

        Returns:
            requests.Response: A response object from the API containing articles and metadata

        """
        if page is None and (parameters is not None or endpoint is not None):
            delay = request_delay if request_delay is not None else self.request_delay
            request_metadata = dict(
                url=self.base_url, query=self.query, page=page, request_delay=delay, caller="search"
            )
            with self.rate_limiter.rate(
                self.config.request_delay if request_delay is None else request_delay, metadata=request_metadata
            ):
                return self.send_request(self.base_url, endpoint=endpoint, parameters=parameters, auth=auth)

        elif page is not None:
            return self.make_request(page, parameters, request_delay=request_delay, endpoint=endpoint, auth=auth)
        else:
            raise APIParameterException("One of 'page' or 'parameters' must be provided")

    def prepare_search(
        self,
        page: Optional[int] = None,
        parameters: Optional[SettingsDictType] = None,
        endpoint: Optional[str] = None,
        *,
        request_delay: Optional[float] = None,
        auth: Optional[AuthBase] = None,
    ) -> requests.PreparedRequest:
        """Prepares the current request given the provided page and parameters.

        The prepared request object can be sent using the `SearchAPI.session.send` method with `requests.Session` and
        `requests_cache.CachedSession` objects.

        Args:
            page (Optional[int]): Page number to query. If provided, parameters are built from the config and this page.
            parameters (Optional[dict[str, Any] | SettingsDict]):
                If provided alone, used as the full parameter set to build the current request.
                If provided together with `page`, these act as additional or overriding parameters on top of
                the built config.
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            request_delay (Optional[float]):
                No-Op: retained to emulate the `.search()` method's parameters to ensure that the value is not included
                in the request parameters.
            auth (Optional[AuthBase]): Optionally enables the addition of an authorization hook onto the request.

        Returns:
            requests.PreparedRequest: A request object that can be sent via `api.session.send`.

        """
        parameters = (
            {k: v for k, v in parameters.items() if k != "request_delay"}
            if isinstance(parameters, (dict, SettingsDict))
            else parameters
        )

        if page is None and (parameters is not None or endpoint is not None):
            return self.prepare_request(self.base_url, endpoint=endpoint, parameters=parameters, auth=auth)
        elif page is not None:
            auth = self.build_auth(parameters, auth=auth)  # if already built in the previous stage, NoOp
            include_api_key = False if auth else None
            parameters = self.build_parameters(page, additional_parameters=parameters, include_api_key=include_api_key)
            return self.prepare_request(self.base_url, endpoint=endpoint, parameters=parameters, auth=auth)
        else:
            raise APIParameterException("One of 'page' or 'parameters' must be provided")

    def make_request(
        self,
        page: int,
        additional_parameters: Optional[SettingsDictType] = None,
        endpoint: Optional[str] = None,
        *,
        request_delay: Optional[float] = None,
        auth: Optional[AuthBase] = None,
    ) -> Response:
        """Constructs and sends a request to the chosen api:

        The parameters are built based on the default/chosen config and parameter map

        Args:
            page (int): The page number to request.
            additional_parameters Optional[dict[str, Any] | SettingsDict]:
                A dictionary of additional overrides not included in the original SearchAPIConfig
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            request_delay (Optional[float]): Overrides the configured request delay for the current request only.
            auth (Optional[AuthBase]): Optionally enables the addition of an authorization hook onto the request.

        Returns:
            requests.Response: The API's response to the request.

        """
        # If auth is provided, remove API keys from the parameter dictionary only. Auth handles the validation and use
        auth = self.build_auth(additional_parameters, auth=auth)
        include_api_key = False if auth else None
        parameters = self.build_parameters(
            page, additional_parameters=additional_parameters, include_api_key=include_api_key
        )

        delay = request_delay if request_delay is not None else self.request_delay
        request_metadata = dict(
            url=self.base_url, query=self.query, page=page, request_delay=delay, caller="send_request"
        )
        with self.rate_limiter.rate(
            self.config.request_delay if request_delay is None else request_delay, metadata=request_metadata
        ):
            response = self.send_request(self.base_url, endpoint=endpoint, parameters=parameters, auth=auth)

        return response

    def prepare_request(
        self,
        base_url: Optional[str] = None,
        endpoint: Optional[str] = None,
        parameters: Optional[SettingsDictType] = None,
        *,
        auth: Optional[AuthBase] = None,
        api_key: Optional[str | SecretStr] = None,
    ) -> requests.PreparedRequest:
        """Prepares a GET request for the specified endpoint with optional parameters.

        This method builds on the
        original base class method by additionally allowing users to specify a custom request directly while also
        accounting for the addition of an API key specific to the API.

        Args:
            base_url (str): The base URL for the API.
            endpoint (Optional[str]): The API endpoint to prepare the request for.
            parameters (Optional[dict[str, Any] | SettingsDict]): Optional query parameters for the request.
            auth (Optional[AuthBase]): Optionally enables the addition of an authorization hook onto the request.
            api_key (Optional[str | SecretStr]): An API key if not previously specified on instantiation.

        Returns:
            requests.PreparedRequest: The prepared request object.

        """
        current_base_url = base_url or self.base_url
        if api_key:
            logger.warning(
                "The `api_key` keyword parameter is now deprecated on `SearchAPI.prepare_request`. Either set the API "
                "key when the `SearchAPI` is initialized, or directly pass an AuthAPIKeyBase subclass instead."
            )
        try:
            # constructs the url with the endpoint

            url = urljoin(current_base_url, endpoint) if endpoint else current_base_url

            parameters = self._validate_parameters(parameters or {})

            # Attempt to set the API key and parameter name if not already set
            if api_key and not self._api_key_exists(parameters):
                api_key_parameter_name = (
                    self.parameter_config.map.api_key_parameter or APIParameterMap.DEFAULT_API_KEY_PARAMETER
                )
                parameters[api_key_parameter_name] = api_key

                # Standardizes auth for API key overrides added during request preparation if auth doesn't exist.
                auth = self.build_auth(parameters, auth=auth, parameter_name=api_key_parameter_name)

            # registers patterns corresponding to data to clean from logs: note patterns are themselves
            # also stored as secrets for greater security
            cleaned_parameters = {}
            for parameter, value in parameters.items():
                self.masker.register_secret_if_exists(parameter, value)
                cleaned_parameters[parameter] = SecretUtils.unmask_secret(value)

            if isinstance(auth, AuthAPIKeyBase):
                # when an `AuthAPIKeyBase` is successfully created, it is guaranteed to have a secret string API key:
                self.masker.register_secret_if_exists(auth.parameter_name, auth.api_key)

            request = requests.Request("GET", url, params=cleaned_parameters, auth=auth)
            prepared_request = request.prepare()
            return prepared_request
        except Exception as e:
            raise RequestCreationException(
                "An unexpected error occurred: The request could "
                f"not be prepared for base_url={current_base_url}, "
                f"endpoint={endpoint}: {e}"
            )

    @staticmethod
    def _api_key_exists(parameters: SettingsDictType) -> bool:
        """Helper method for determining whether an API key exists in the dictionary of provided parameters.

        Args:
            parameters (dict[str, Any] | SettingsDict): Optional query parameters for the request.

        Returns:
            bool: Indicates whether or not an API key exists with a non-empty value.

        """
        for k in parameters:
            normalized = re.sub(rf"[{re.escape(punctuation)}]", "", k).lower()
            if normalized == "apikey":
                return bool(parameters[k])
        return False

    @contextmanager
    def with_config(
        self,
        config: Optional[SearchAPIConfig] = None,
        parameter_config: Optional[APIParameterConfig] = None,
        provider_name: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Iterator[SearchAPI]:
        """Temporarily modifies the SearchAPI's SearchAPIConfig and/or APIParameterConfig and namespace.

        You can provide a config, a parameter_config, or a provider_name to fetch defaults. Explicitly provided configs
        take precedence over provider_name, and the context manager will revert changes to the parameter mappings and
        search configuration afterward.

        Args:
            config (Optional[SearchAPIConfig]):
                Temporary SearchAPIConfig to use within the context to control where and how response records are
                retrieved.
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
        self, provider_name: Optional[str] = None, query: Optional[str] = None, **api_specific_parameters: Any
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

    def describe(self) -> dict[str, Any]:
        """A helper method used that describe accepted configuration for the current provider or user-defined parameter
        mappings.

        Returns:
            dict[str, Any]: A dictionary describing valid config fields and provider-specific API parameters for the
            current provider (if applicable).

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
        """Helper method for quickly showing a representation of the overall structure of the SearchAPI.

        The helper function, generate_repr_from_string helps produce human-readable representations of the core
        structure of the SearchAPI.

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
