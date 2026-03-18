# /security/patterns.py
"""The scholar_flux.security.patterns module implements pattern matching utilities for sensitive string masking.

This module defines the foundational patterns required to implement lightweight fixed/regular expression pattern
matching objects for masking sensitive strings in both text and JSON-formatted dictionaries.

Classes:
    MaskingPattern:
        Implements the abstract base class that defines how MaskingPatterns are created and formatted.
    MaskingPatternSet:
        Defines a subclass of a set that accepts only subclasses of MaskingPatterns for robustness.
    KeyMaskingPattern:
        Defines the class and methods necessary to mask text based on the presence or absence of a specific field name
        when determining which patterns to mask.
    StringMaskingPattern:
        Defines the class and methods necessary to mask text based on the presence or absence of specific patterns.
        These patterns can either be fixed or regular expressions and accept both case-sensitive and case-insensitive
        pattern matching settings.

"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pydantic import Field
from pydantic.dataclasses import dataclass
from typing import Iterable
from pydantic import SecretStr
import re
from scholar_flux.security.utils import SecretUtils


@dataclass(frozen=True)
class MaskingPattern(ABC):
    """The base class for creating MaskingPattern objects that can be used to mask fields based on defined rules."""

    name: str
    pattern: str | SecretStr
    apply_to_text: bool = Field(default=True, kw_only=True)  # Whether to use this pattern in mask_text()
    apply_to_dict: bool = Field(default=False, kw_only=True)  # Whether this pattern should be applied to dictionaries

    @abstractmethod
    def apply_masking(self, text: str) -> str:
        """Base method that will be overridden by subclasses to later remove sensitive values and fields from text."""
        ...

    def __hash__(self) -> int:
        """Resolves the current pattern into an identifying hash using the self._identity_key() private method.

        This method ensures that patterns can be stored in dictionaries and sets and replaced with new
        pattern-specific settings when needed.

        Returns:
            int: An integer-based hash of the current pattern.

        """
        return hash(self._identity_key())

    def __eq__(self, other: object) -> bool:
        """Uses the class-specific `_identity_key()` method to check if the current pattern is equal to another."""
        if not isinstance(other, type(self)):
            return False
        return self._identity_key() == other._identity_key()

    @abstractmethod
    def _identity_key(self) -> str:
        """This private method, when overridden, allows for hash-based pattern storage and identification."""
        ...

    @classmethod
    def _split_pattern(cls, pattern: str) -> list[str]:
        """Helper method that splits fields by `pipe` to separate patterns as a list of strings."""
        return re.split(r"(?<!\\)\|", pattern)


@dataclass(frozen=True)
class KeyMaskingPattern(MaskingPattern):
    """Masks values associated with specific keys/fields/parameters in text and API requests.

    The KeyMaskingPattern identifies fields in dumped JSON-formatted data that are commonly prepared in the
    creation of request URLs. After identifying the assigned fixed-string field or key in a request URL or
    string-formatted dictionary, the pattern conditionally masks its associated value using a fixed or regular
    expression pattern.

    By default, the masking pattern is set to filter string combinations of dashes and alphanumeric fields that
    are commonly observed in API keys, secrets, etc. The `pattern` parameter can be overridden to identify sensitive
    text such as birthdays, combinations of digits, and addresses using regular expressions.

    Attributes:
        name (str):
            The name to be associated with a particular pattern. Facilitates the identification and
            retrieval of pattern masks by name/category in later steps.
        field (str):
            The fixed field string to look for when determining whether to mask a specific parameter.
        pattern (str):
            The pattern that will be used to identify and mask sensitive fields when its corresponding field/JSON key
            has been located.
        replacement (str):
            Indicates the replacement string for the value in the key-value pair if matched ('***' by default)
        use_regex (bool):
            Indicates whether the current function should use regular expressions
        ignore_case (bool):
            whether we should consider case when determining whether or not to filter a string. (True by default)
        mask_pattern (bool):
            Indicates whether we should, by default, mask pattern strings that are registered in the MaskingPattern.
            This is True by default.
        apply_to_text (bool):
            Whether this pattern should be applied during mask_text() operations. Defaults to True.
            Set to False for dict-only patterns that would cause false positives in text.
        apply_to_dict (bool):
            Whether this pattern should be applied during mask_dict() operations. Defaults to True.
            Set to False for text-only patterns (like URL patterns) that don't apply to dictionary keys.

    """

    name: str
    field: str = Field(default=..., min_length=1)
    pattern: str | SecretStr = r"[A-Za-z0-9\-_]+"
    replacement: str = "***"
    use_regex: bool = True
    ignore_case: bool = True
    mask_pattern: bool = True
    apply_to_dict: bool = True

    def __post_init__(self) -> None:
        """Post initialization step that prepares the `pattern` attribute for use with `.apply_masking()`.

        This implementation can optionally mask the pattern attribute on post initialization to ensure that the current
        pattern, itself, doesn't inadvertently link sensitive patterns to logs.

        """
        if self.mask_pattern and not isinstance(self.pattern, SecretStr):
            object.__setattr__(self, "pattern", SecretUtils.mask_secret(self.pattern))

    def matches_key(self, key: str) -> bool:
        """Checks if a dictionary key matches this pattern's field.

        This method returns True when the field of the current KeyMaskingPattern matches the key. If the field doesn't
        match, False is returned. A case insensitive match is only performed if `KeyMaskingPattern.ignore_case=True`.

        Args:
            key (str): The dictionary key to check

        Returns:
            bool: True if the key matches, False otherwise

        Example:
            >>> pattern = KeyMaskingPattern(name="test", field="password")
            >>> pattern.matches_key("password")
            # OUTPUT: True
            >>> pattern.matches_key("PASSWORD") # (ignore_case=True by default)
            # OUTPUT: True
            >>> pattern.matches_key("pass") # (exact match required)
            # OUTPUT: False

        """
        if not isinstance(key, str):
            return False

        return key.lower() == self.field.lower() if self.ignore_case else key == self.field

    def apply_masking(self, text: str) -> str:
        """Removes sensitive fields from text based on the current KeyMaskingPattern's defined settings.

        For the current pattern to trigger, the current field must match the string field of a dictionary or the name
        of the field found in the current text string. Masking behavior can be customized based on the defined settings
        of the current masking pattern (`field`, `pattern`, `replacement`, and `ignore_case`)

        Args:
            text (str): The text to clean of sensitive fields

        """
        flags = re.IGNORECASE if self.ignore_case else 0
        value_pattern = SecretUtils.unmask_secret(self.pattern)
        if not self.use_regex:
            value_pattern = re.escape(value_pattern)
        pattern = (
            rf"""(?P<field>["']?{re.escape(self.field)}["']?\s*[:\=]\s*["']?){value_pattern}(?P<endpattern>["']?)"""
        )
        replacement = rf"\g<field>{self.replacement}\g<endpattern>"
        return re.sub(pattern, replacement, text, flags=flags)

    def _identity_key(self) -> str:
        """Identifies the current pattern based on name, field, pattern, and class."""
        return str((type(self).__name__, self.name, self.field, SecretUtils.unmask_secret(self.pattern)))


class FuzzyKeyMaskingPattern(KeyMaskingPattern):
    """A KeyMaskingPattern subclass that allows the field parameter to use regular expressions field pattern matching.

    Attributes:
        name (str):
            The name to be associated with a particular pattern - can help in later identification and
            retrieval of rules associated with pattern masks of a particular category.
        field (str):
            The regular expression field to look for when determining whether to mask a specific parameter.
        pattern (str):
            The pattern to use to remove sensitive fields, contingent on a parameter being defined. By default, the
            pattern is set to allow for the removal dashes and alphanumeric fields but can be overridden based on API
            specific specifications.
        replacement (str):
            Indicates the replacement string for the value in the key-value pair if matched ('***' by default)
        use_regex (bool):
            Indicates whether the current function should use regular expressions
        ignore_case (bool):
            whether we should consider case when determining whether or not to filter a string. (True by default)
        mask_pattern (bool):
            Indicates whether we should, by default, mask pattern strings that are registered in the MaskingPattern.
            This is True by default.
        apply_to_text (bool):
            Whether this pattern should be applied during mask_text() operations. Defaults to True.
        apply_to_dict (bool):
            Whether this pattern should be applied during mask_dict() operations. Defaults to True.

    """

    def matches_key(self, key: str) -> bool:
        """Checks if a dictionary key matches this pattern's field using regular expressions.

        This method returns True if the field of the current `FuzzyKeyMaskingPattern`, when used as a regular
        expression, matches the provided key and false otherwise.

        Args:
            key (str): The dictionary key to check

        Returns:
            bool: True if the key matches the regex pattern, False otherwise

        Example:
            >>> pattern = FuzzyKeyMaskingPattern(name="test", field="pass(word)?")
            >>> pattern.matches_key("password")
            # OUTPUT: True
            >>> pattern.matches_key("pass")
            # OUTPUT: True
            >>> pattern.matches_key("Pass") # (ignore_case=True is the default)
            # OUTPUT: True
            >>> pattern.matches_key("passphrase") # (regex matching)
            # OUTPUT: True

        """
        if not isinstance(key, str):
            return False

        flags = re.IGNORECASE if self.ignore_case else 0
        return bool(re.search(self.field, key, flags=flags))

    def apply_masking(self, text: str) -> str:
        """Uses fuzzy field matching to identify fields containing sensitive data in text.

        This method is revised to account for circumstances where several fields might be present in the same
        text string using the `|` delimiter. The masker can be customized using the following fields:
        `field`, `pattern`, `replacement`, `use_regex`, and `ignore_case`.

        Args:
            text (str): The text to clean of sensitive fields

        """
        flags = re.IGNORECASE if self.ignore_case else 0
        value_pattern = SecretUtils.unmask_secret(self.pattern)
        if not self.use_regex:
            value_pattern = re.escape(value_pattern)

        replacement = rf"\g<field>{self.replacement}\g<endpattern>"
        for field in sorted(self._split_pattern(self.field), key=len, reverse=True):
            pattern = rf"""(?P<field>["']?{field}["']?\s*[:\=]\s*["']?){value_pattern}(?P<endpattern>["']?)"""
            text = re.sub(pattern, replacement, text, flags=flags)

        return text


@dataclass(frozen=True)
class StringMaskingPattern(MaskingPattern):
    """Masks values associated with a particular pattern or fixed string in text and API requests.

    Attributes:
        name (str):
            The name to be associated with a particular pattern - can help in later identification and
            retrieval of rules associated with pattern masks of a particular category.
        pattern (str):
            The pattern to use to remove sensitive fields, contingent on a parameter being defined. By default, the
            pattern is set to allow for the removal dashes and alphanumeric fields but can be overridden based on API
            specific specifications.
        replacement (str):
            Indicates the replacement string for the value in the string if matched ('***' by default)
        use_regex (bool):
            Indicates whether the current function should use regular expressions
        ignore_case (bool):
            whether we should consider case when determining whether or not to filter a string. (True by default)
        mask_pattern (bool):
            Indicates whether we should, by default, mask pattern strings that are registered in the MaskingPattern.
            This is True by default.
        apply_to_text (bool):
            Whether this pattern should be applied during mask_text() operations. Defaults to True.
        apply_to_dict (bool):
            Whether this pattern should be applied to dictionary values during mask_dict() operations. Defaults to False.
            String patterns typically match text content (like URLs) rather than dict keys or values.


        Note: By default, this class does not operate on dictionaries unless explicitly configured to do so.

    """

    name: str
    pattern: str | SecretStr
    replacement: str = "***"
    use_regex: bool = True
    ignore_case: bool = True
    mask_pattern: bool = True

    def __post_init__(self) -> None:
        """Uses the mask_pattern field to determine whether or not to mask a particular string."""
        if self.mask_pattern and not isinstance(self.pattern, SecretStr):
            object.__setattr__(self, "pattern", SecretUtils.mask_secret(self.pattern))

    def apply_masking(self, text: str) -> str:
        """Removes sensitive strings or patterns from text based on the defined settings of the `StringMaskingPattern`.

        For the current pattern to trigger, the registered pattern must match the text exactly if
        `use_regex=False`. Otherwise, the pattern is treated as a regular expression. Case sensitivity is
        determined by the `ignore_case` attribute.

        Masking behavior can be further customized based on the defined settings of the current masking pattern based on
        the attributes specified for `pattern`, `replacement`, `use_regex`, and `ignore_case`.

        Args:
            text (str): The text to clean of sensitive fields
        Returns:
            text (str): The text after scrubbing sensitive fields

        """
        flags = re.IGNORECASE if self.ignore_case else 0
        pattern = SecretUtils.unmask_secret(self.pattern)
        if not self.use_regex:
            pattern = re.escape(pattern)
        return re.sub(pattern, self.replacement, text, flags=flags)

    def _identity_key(self) -> str:
        """Identifies the current pattern based on name, field, pattern, and class."""
        return str((type(self).__name__, self.name, SecretUtils.unmask_secret(self.pattern)))


class MaskingPatternSet(set[MaskingPattern]):
    """Subclasses the `set` to implement the type-safe storage of MaskingPatterns.

    As a result, the robustness of operations requiring sensitive pattern masking is increased, reducing the likelihood
    of unexpected errors during response retrieval and the redaction of sensitive parameters with ScholarFlux.

    """

    def __init__(self) -> None:
        """Initializes the MaskingPatternSet as an empty set."""
        super().__init__()

    def add(self, item: MaskingPattern) -> None:
        """Overrides the basic `add` method to ensure that each `item` is type-checked prior to entering the set."""
        if not isinstance(item, MaskingPattern):
            raise TypeError(f"Expected a MaskingPattern, got {type(item)}")
        super().add(item)

    def update(self, *others: Iterable[MaskingPattern]) -> None:
        """Overrides the basic `update` method to ensure that all `items` are type-checked prior to entering the set."""
        for patterns in others:
            if isinstance(patterns, MaskingPattern):
                super().add(patterns)
            else:
                for element in patterns:
                    if not isinstance(element, MaskingPattern):
                        raise TypeError(f"Expected a masking pattern, received type {type(element)}")
                super().update(patterns)


__all__ = ["MaskingPattern", "KeyMaskingPattern", "FuzzyKeyMaskingPattern", "StringMaskingPattern", "MaskingPatternSet"]
