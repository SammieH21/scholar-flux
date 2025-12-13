# /api/models/response_history.py
"""The scholar_flux.api.models.response_history module implements the ResponseHistoryRegistry for recording responses.

This class is later used as a class-level attribute to record the most N newest responses per provider for the
calculation of accurate request delays.

"""
from __future__ import annotations
from typing import Optional
from scholar_flux.api.models.base_provider_dict import BaseProviderDict
from scholar_flux.utils.provider_utils import ProviderConfig
from scholar_flux.api.models.responses import ProcessedResponse, ErrorResponse
from scholar_flux.exceptions import APIParameterException
from scholar_flux.api.providers import provider_registry
import threading
import logging

logger = logging.getLogger(__name__)


class ResponseHistoryRegistry(BaseProviderDict):
    """The ResponseHistoryRegistry is responsible for storing a sorted list of responses for later retrieval.

    This class has its utility in multi-orchestrated searches to a single provider across workflows and coordinators.

    Note that the ResponseHistoryRegistry uses the ProviderConfig._normalize_name to ignore underscores and case-sensitivity.

    Methods:
        - ResponseHistoryRegistry.get: resolves a provider name to an API response if it exists in the registry.
        - ResponseHistoryRegistry.get_from_url: resolves a provider URL to an API response if it exists in the registry.

    """

    def __init__(self, *args, **kwargs):
        """Initializes the `ResponseHistoryRegistry` with a thread lock to enforce threaded dictionary operations."""
        self._lock = threading.Lock()
        super().__init__(*args, **kwargs)

    def __getitem__(self, key: str) -> ErrorResponse | ProcessedResponse:
        """Attempt to retrieve a ProviderConfig instance for the given provider name.

        Args:
            provider_name (str): Name of the default provider

        Returns:
            ErrorResponse | ProcessedResponse: an APIResponse for the provider if it exists.

        """
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(
        self,
        key: str,
        value: ErrorResponse | ProcessedResponse,
    ) -> None:
        """Allows for the addition of APIResponse types to the `ResponseHistoryRegistry`.

        This handles the implicit validation necessary to ensure that keys are strings and values are API Response
        subclasses.

        Args:
            key (str): Name of the provider to add to the registry
            value (ErrorResponse | ProcessedResponse): The configuration of the API Provider

        """
        try:
            if not isinstance(value, (ErrorResponse, ProcessedResponse)):
                raise TypeError(
                    f"The value provided to the ResponseHistoryRegistry is invalid. "
                    f"Expected a ErrorResponse or ProcessedResponse, received {type(value)}"
                )

            with self._lock:
                super().__setitem__(key, value)
        except (TypeError, ValueError) as e:
            raise APIParameterException(e) from e

    def __delitem__(self, key: str) -> None:
        """Thread-safe method override that deletes a key from the current dictionary if it exists."""
        with self._lock:
            super().__delitem__(key)

    def __contains__(self, key: object) -> bool:
        """Thread-safe method override that indicates whether a response for a key (provider) exists in the history."""
        with self._lock:
            return super().__contains__(key)

    def add(self, provider_name: str, response: ProcessedResponse | ErrorResponse) -> None:
        """Helper method for adding a new response to the `ResponseHistoryRegistry`."""
        self[provider_name] = response

    def remove(self, provider_name: str) -> None:
        """Helper method for removing an ErrorResponse or ProcessedResponse from the `ResponseHistoryRegistry`."""
        provider_name = ProviderConfig._normalize_name(provider_name)
        if response := self.data.pop(provider_name, None):
            logger.debug(
                f"Removed the {type(response)} for the provider, '{provider_name}' from the response history registry"
            )

    def get_from_url(self, provider_url: Optional[str]) -> Optional[ProcessedResponse | ErrorResponse]:
        """Attempt to retrieve a ProcessedResponse or ErrorResponse instance for the given provider from a URL.

        This method retrieves responses by resolving the provided URL to the provider's base URL after normalization.
        If a provider does not exist in the response history, a value of None will be returned instead.

        Args:
            provider_url (Optional[str]): URL of the provider to look up.

        Returns:
            Optional[ProcessedResponse | ErrorResponse]:
                The last stored response for a provider if it has an entry in the response history. Otherwise None.

        """
        if provider_config := provider_registry.get_from_url(provider_url):
            return self.data.get(provider_config.provider_name)
        return None


__all__ = ["ResponseHistoryRegistry"]
