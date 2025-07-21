from pydantic import BaseModel, field_validator
from typing import Dict, Optional, Union, TYPE_CHECKING
from ...utils import validate_url
from .base import BaseAPIParameterMap
from ...exceptions.api_exceptions import APIParameterException

import logging
logger = logging.getLogger(__name__)

class ProviderInfo(BaseModel):
    """Config for specifying Parameter Information by Provider"""
    parameter_map: BaseAPIParameterMap
    name: str
    base_url: str
    records_per_page: int = 25
    request_delay: float = 6.1
    docs_url: Optional[str] = None

    def search_config_defaults(self):
        """Convenience Method for retrieving ProviderInfo fields as a dict"""
        return dict(name=self.name,
                    base_url=self.base_url,
                    records_per_page=self.records_per_page,
                    request_delay=self.request_delay
                   )

    @field_validator('base_url')
    def validate_base_url(cls, v: str) -> str:
        """Validates the current url and raises a APIParameterException if invalid"""
        if not isinstance(v, str) or not validate_url(v):
            logger.error("The URL provided to the ProviderInfo is invalid: {v}")
            raise APIParameterException(f"The URL provided to the ProviderInfo is invalid: {v}")
        return v

    @field_validator('docs_url')
    def validate_docs_url(cls, v: Optional[str]) -> Optional[str]:
        """Validates the documentation url and raises a APIParameterException if invalid"""
        if v is not None and not validate_url(v):
            logger.error("The URL provided to the ProviderInfo is invalid: {v}")
            raise APIParameterException(f"The URL provided to the ProviderInfo is invalid: {v}")
        return v


