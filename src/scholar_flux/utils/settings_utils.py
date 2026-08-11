# /utils/settings_utils.py
"""Defines settings utility helpers for handling settings with potentially sensitive information in the console."""

from __future__ import annotations

from typing import Any, Annotated, TypeGuard
from typing_extensions import TypeVar
from collections import UserDict
from pydantic import BeforeValidator, GetCoreSchemaHandler

from pydantic_core import CoreSchema, core_schema

from scholar_flux.security import masker
from scholar_flux.utils.helpers import handle_exception


class SettingsDict(UserDict[str, Any]):
    """Dictionary wrapper defining the types of key-value pairs, masking sensitive data representations when printed."""

    def __repr__(self) -> str:
        """Masks output by default when viewing the current dictionary."""
        masked_dict = masker.mask_value(self.data)
        return str(masked_dict)

    def __setitem__(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Overrides the `__setitem__` dictionary method to validate the type of the key before its addition.

        Args:
            key (str): The setting to add to the `SettingsDict`.
            value (Any): The value associated with the setting to add to the `SettingsDict`.

        """
        if not isinstance(key, str):
            raise TypeError(
                f"The key provided to the SettingsDict is invalid. Expected a str, but received {type(key)}"
            )

        super().__setitem__(key, value)

    @classmethod
    def validate_settings_dict(cls, data: dict[str, Any] | SettingsDict) -> SettingsDict:
        """Validates the current dictionary, returning a `SettingsDict` when valid."""
        return data if cls.is_settings_like(data, raise_on_error=True) and isinstance(data, SettingsDict) else cls(data)

    @classmethod
    def is_settings_like(
        cls, data: object | SettingsLike, *, verbose: bool | None = None, raise_on_error: bool = False
    ) -> TypeGuard[SettingsLike]:
        """Identifies whether an object is a SettingsDict containing keyword parameters or a settings-like mapping."""
        try:
            if not isinstance(data, (dict, SettingsDict)):
                raise TypeError(f"Expected a valid settings dictionary, but received type {type(data).__name__}.")
            if not all(isinstance(field, str) for field in data):
                raise ValueError("Expected a valid settings dictionary, but at least one field is not a string.")
            return True
        except (TypeError, ValueError) as e:
            log_exception = verbose if verbose is not None else bool(raise_on_error)
            handle_exception(e, raise_on_error=raise_on_error, verbose=log_exception)
        return False

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Retrieves the schema defining the SettingsDict data type for compatibility with Pydantic."""
        # This tells Pydantic to validate it as a standard dict
        return core_schema.dict_schema(
            keys_schema=handler.generate_schema(str),
            values_schema=handler.generate_schema(Any),
        )


SettingsLike = TypeVar("SettingsLike", bound=dict[str, Any] | SettingsDict)
SettingsDictType = Annotated[
    SettingsLike,
    BeforeValidator(SettingsDict.validate_settings_dict),
]

__all__ = ["SettingsDict", "SettingsLike", "SettingsDictType"]
