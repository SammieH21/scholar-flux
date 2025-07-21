from pydantic import BaseModel,  Field, field_validator
from typing import Dict, Optional, Any, Annotated, Union, ClassVar
from urllib.parse import urlparse
from scholar_flux.utils import validate_url
from scholar_flux.api.models.providers import PROVIDER_DEFAULTS
from scholar_flux.exceptions.api_exceptions import APIParameterException
import re
import logging

logger = logging.getLogger(__name__)

class SearchAPIConfig(BaseModel):
    """
    The SearchAPIConfig class provides the core tools necessary
    to set and interact with the API. The SearchAPI uses this
    class to retrieve data from an API using universal parameters
    to simplify the process of retrieving raw responses.

    Attributes:
        base_url (str): Indicates the API url where we'll be searching and retrieving data
        records_per_page (int): Control the number of records that will appear on each page
        api_key (Optional[str]): This is an API specific parameter for validation of the
                                 current user's identity
        request_delay (float): Indicates the total time that we should put in between
                               each request to the current API

    """

    base_url: str = Field(
        default="https://api.plos.org/search",
        description="Base URL for the article API",
    )
    records_per_page: int = Field(25, ge=1, le=1000, description="Number of records per page (1-100)")
    api_key: Optional[str] = Field(None, min_length=20, max_length=200, description="API key if required")
    request_delay: float = Field(
        6.1, gt=0, description="Minimum delay between requests in seconds"
    )

    DEFAULT_RECORDS_PER_PAGE: ClassVar[int] = 25
    DEFAULT_REQUEST_DELAY: ClassVar[float] = 6.1

    @field_validator('base_url')
    def validate_url(cls, v):
        """Validates the current url and raises a APIParameterException if invalid"""
        if  not validate_url(v):
            logger.error("The URL provided to the SearchAPIConfig is invalid: {v}")
            raise APIParameterException(f"The URL provided to the SearchAPIConfig is invalid: {v}")
        return v

    @field_validator("request_delay",mode="before")
    def set_default_request_delay(cls, v):
        """Sets the request_delay (delay between each request) with the default if the supplied value is not valid"""
        if not v or v < 0:
            return  cls.DEFAULT_REQUEST_DELAY
        return v

    @field_validator("records_per_page",mode="before")
    def set_records_per_page(cls, v):
        """Sets the records_per_page parameter with the default if the supplied value is not valid"""
        if not v or v < 0:
            return  cls.DEFAULT_RECORDS_PER_PAGE
        return v

    @property
    def url_basename(self)->str:
        """
        Extracts the main site name from a URL by removing everything before 'www' and everything
        including and after the top-level domain.

        Args:
            url (str): The URL to process.

        Returns:
            str: The main site name.
        """
        # Parse the URL to extract the hostname
        parsed_url = urlparse(self.base_url)
        hostname = parsed_url.hostname

        if not hostname:
            # Handle case when urlparse fails to get hostname
            hostname = self.base_url.split('/')[0]

        # Regular expression to match the main site name in the hostname
        pattern = re.compile(r'^(?:.*\.)?([a-zA-Z0-9-_]+)\.(?:com|org|net|ac\.uk|io|gov|edu)')
        match = pattern.search(hostname)

        if match:
            return match.group(1)
        else:
            return ""

    @classmethod
    def from_defaults(cls,
                      # query: str,
                      provider_name: str,
                      api_key: Optional[str] = None,
                      **kwargs
                      ) -> "SearchAPIConfig":
        """
        Uses the default configuration for the chosen provider to
        create a SearchAPIConfig object containing configuration parameters

        Returns:
            SearchAPIConfig: a default APIConfig object based on the chosen parameters
        """
        provider=PROVIDER_DEFAULTS.get(provider_name)

        if not provider:
            raise NotImplementedError(f"Provider '{provider_name}' config not implemented")

        class_params = provider.search_config_defaults()
        if kwargs:
            class_params=class_params | {key: value for key, value in kwargs.items() if value is not None}

        return cls(**class_params, api_key=api_key)
