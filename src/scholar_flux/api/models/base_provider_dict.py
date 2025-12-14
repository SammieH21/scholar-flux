# /api/models/base_provider_dict.py
"""The scholar_flux.api.models.base_provider_dict.py module implements a BaseProviderDict to extend the dictionary and
resolve provider names to a generic key, handling the normalization of provider names for consistent access."""
from __future__ import annotations
from typing import Any
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.utils.repr_utils import generate_repr_from_string
from collections import UserDict


class BaseProviderDict(UserDict[str, Any]):
    """The BaseProviderDict extends the dictionary to resolve minor naming variations in keys to the same provider name.

    The BaseProviderDict uses the `ProviderConfig._normalize_name` method to ignore underscores and case-sensitivity.

    """

    def __contains__(self, key: object) -> bool:
        """Helper method for determining whether a specific provider name after normalization can be found within the
        current ProviderDict.

        Args:
            key (str): Name of the default provider

        Returns:
            bool: indicates the presence or absence of a key in the dictionary

        """

        if isinstance(key, str):
            key = self._normalize_name(key)
            return key in self.data
        return False

    def __getitem__(self, key: str) -> Any:
        """Attempt to retrieve a value instance for the given provider name.

        Args:
            provider_name (str): Name of the default provider

        Returns:
            Any: The value associated with the current provider

        """

        key = self._normalize_name(key) if isinstance(key, str) else key
        return super().__getitem__(key)

    def __setitem__(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Adds a key-value pair to the BaseProviderDict with key normalization.

        This method overrides the original dict.__setitem__ method to verify that the key used as a provider name
        is a non-empty string.

        Args:
            key (str): Name of the provider to add to the dictionary
            value (Any): The value to associate with the provider

        Raises:
            TypeError: If the current key is not a string
            ValueError: If the normalized key is an empty string

        """

        # normalizes the key/provider before ever registering
        normalized_key = self._normalize_name(key)

        if not normalized_key:
            raise ValueError(f"The key provided to the {self.__class__.__name__} is empty. Expected a non-empty string")

        super().__setitem__(normalized_key, value)

    def __delitem__(self, key: str) -> None:
        """Deletes an element from the ProviderDict for the given provider.

        Args:
            key (str): Name of the default provider

        Raises:
            KeyError: If the current key does not exist in the dictionary

        """

        key = self._normalize_name(key) if isinstance(key, str) else key
        return super().__delitem__(key)

    @classmethod
    def _normalize_name(cls, key: str) -> str:
        """Helper method that is used to validate and normalize provider names.

        Args:
            key (str): Name of the provider

        Returns:
            str: The normalized provider name

        Raises:
            TypeError: If the current key is not a string

        """

        # Check if the key already exists and handle overwriting behavior
        if not isinstance(key, str):
            raise TypeError(
                f"The key provided to the {cls.__name__} is invalid. Expected a string, received {type(key)}"
            )

        normalized_key = ProviderConfig._normalize_name(key)
        return normalized_key

    @property
    def providers(self) -> list[str]:
        """Returns a list containing the names of all (keys) in the current registry.

        Returns:
            A complete list of all keys shown in the current registry

        """
        return list(self.data)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the BaseProviderDict or subclass."""
        class_name = self.__class__.__name__
        dictionary_elements = self.data

        return generate_repr_from_string(
            class_name, dictionary_elements, flatten=flatten, show_value_attributes=show_value_attributes, as_dict=True
        )

    def __repr__(self) -> str:
        """Helper method for displaying the config in a user-friendly manner."""
        return self.structure()


__all__ = ["BaseProviderDict"]
