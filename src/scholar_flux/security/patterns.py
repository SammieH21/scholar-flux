# /security/patterns.py
"""
The scholar_flux.security.patterns module implements the foundational patterns required to implement
a light-weight fixed/regex pattern matching utility that determines keys to mask in both text
and json-formatted parameter dictionaries.

Classes:
    MaskingPattern: Implements the abstract base class that defines how MaskingPatterns are created and formatted.
    MaskingPatternSet: Defines a subclass of a set that excepts only subclasses of MaskingPatterns for robustness.
    KeyMaskingPattern: Defines the class and methods necessary to mask text based on the presence or absence of
                       a specific field name when determining what patterns to mask.
    StringMaskingPattern: Defines the class and methods necessary to mask text based on the presence or absence of
                          specific patterns. These patterns can either be fixed or regular expressions,
                          and accept both case-sensitive and case-insensitive pattern matching settings.
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
    """
    The base class for creating MaskingPattern objects
    that can be used to mask fields based on defined rules
    """

    name: str
    pattern: str | SecretStr

    @abstractmethod
    def apply_masking(self, text: str) -> str:
        """
        Base method that will be overridden by subclasses to later remove
        sensitive values and fields from text
        """
        pass

    def __hash__(self) -> int:
        """
        A helper method for resolving a pattern into an identifying
        hash using the self._identity_key() private method to be later
        overridden by subclasses.
        The purpose of this method is to ensure patterns can be stored
        in dictionaries and lists
        """
        return hash(self._identity_key())

    def __eq__(self, other: object) -> bool:
        """
        Uses the class identity key method in order to determine whether the
        pattern ca be considered equal to that of another pattern minus
        the instance-specific settings
        """
        if not isinstance(other, type(self)):
            return False
        return self._identity_key() == other._identity_key()

    @abstractmethod
    def _identity_key(self) -> str:
        """
        This private method, when overridden, allows the current class to
        resolve into a hash for easier comparisons to other patterns of the
        same type
        """
        pass


@dataclass(frozen=True)
class KeyMaskingPattern(MaskingPattern):
    """
    Masks values associated with specific keys/fields/parameters in text and API requests.
    Attributes:
        name: (str) the name to be associated with a particular pattern - can help in later
                    identification and retrieval of rules associated with pattern masks of
                    a particular category.
        field (str): The field to look for when determining whether to mask a specific parameter
        pattern (str): The pattern to use to remove sensitive fields, contingent on a parameter being defined.
                       By default, the pattern is set to allow for the removal dashes and alphanumeric fields
                       but can be overridden based on API specific specifications
        replacement (str): Indicates the replacement string for the value in the key-value pair if matched ('***' by default)
        use_regex (bool): Indicates whether the current function should use regular expressions
        ignore_case (bool): whether we should consider case when determining whether or not to filter a string. (True by default)
        mask_pattern (bool): indicates whether we should, by default, mask pattern strings that are registered
                             in the MaskingPattern. This is True by default.
    """

    name: str
    field: str = Field(default=..., min_length=1)
    pattern: str | SecretStr = r"[A-Za-z0-9\-_]+"
    replacement: str = "***"
    use_regex: bool = True
    ignore_case: bool = True
    mask_pattern: bool = True

    def __post_init__(self):
        """Uses the mask_pattern field to determine whether or not to mask a particular string"""
        if self.mask_pattern and not isinstance(self.pattern, SecretStr):
            object.__setattr__(self, "pattern", SecretUtils.mask_secret(self.pattern))

    def apply_masking(self, text: str) -> str:
        """
        Uses the defined settings in order to remove sensitive fields from text
        based on the attributes specified for field, pattern, replacement, and
        ignore case.

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
        """Identifies the current pattern based on name, field, pattern, and class"""
        return str((type(self).__name__, self.name, self.field, SecretUtils.unmask_secret(self.pattern)))


@dataclass(frozen=True)
class StringMaskingPattern(MaskingPattern):
    """
    Masks values associated with a particular pattern or fixed string in text and API requests.
    Attributes:
        name: (str) the name to be associated with a particular pattern - can help in later
                    identification and retrieval of rules associated with pattern masks of
                    a particular category.
        pattern (str): The pattern to use to remove sensitive fields, contingent on a parameter being defined.
                       By default, the pattern is set to allow for the removal dashes and alphanumeric fields
                       but can be overridden based on API specific specifications
        replacement (str): Indicates the replacement string for the value in the string if matched ('***' by default)
        use_regex (bool): Indicates whether the current function should use regular expressions
        ignore_case (bool): whether we should consider case when determining whether or not to filter a string. (True by default)
        mask_pattern (bool): indicates whether we should, by default, mask pattern strings that are registered
                             in the MaskingPattern. This is True by default.
    """

    name: str
    pattern: str | SecretStr
    replacement: str = "***"
    use_regex: bool = True
    ignore_case: bool = True
    mask_pattern: bool = True

    def __post_init__(self):
        """Uses the mask_pattern field to determine whether or not to mask a particular string"""
        if self.mask_pattern and not isinstance(self.pattern, SecretStr):
            object.__setattr__(self, "pattern", SecretUtils.mask_secret(self.pattern))

    def apply_masking(self, text: str) -> str:
        """
        Uses the defined settings in order to remove sensitive fields from text
        based on the attributes specified for pattern, replacement, use_regex, and
        ignore case.

        Args:
            text (str): The text to clean of sensitive fields
        Returns
            text (str): The text after scrubbing sensitive fields

        """

        flags = re.IGNORECASE if self.ignore_case else 0
        pattern = SecretUtils.unmask_secret(self.pattern)
        if not self.use_regex:
            pattern = re.escape(pattern)
        return re.sub(pattern, self.replacement, text, flags=flags)

    def _identity_key(self) -> str:
        """Identifies the current pattern based on name, field, pattern, and class"""
        return str((type(self).__name__, self.name, SecretUtils.unmask_secret(self.pattern)))


class MaskingPatternSet(set[MaskingPattern]):
    """
    Defines the subclass of a set that implements type safety to ensure that only subclasses of
    MaskingPatterns can be added. As a result, robustness is increased, and the likelihood of
    unsuspecting errors decreases at runtime when using the scholar_flux API for response retrieval.
    """

    def __init__(self):
        """Initializes the MaskingPatternSet as an empty set"""
        super().__init__()

    def add(self, item: MaskingPattern) -> None:
        """Overrides the basic `add` method to ensure that each `item` is typed checked prior to entering the set"""
        if not isinstance(item, MaskingPattern):
            raise TypeError(f"Expected a MaskingPattern, got {type(item)}")
        super().add(item)

    def update(self, *others: Iterable[MaskingPattern]) -> None:
        """Overrides the basic `update` method to ensure that all `items` are typed checked prior to entering the set"""
        for patterns in others:
            if isinstance(patterns, MaskingPattern):
                super().add(patterns)
            else:
                for element in patterns:
                    if not isinstance(element, MaskingPattern):
                        raise TypeError(f"Expected a masking pattern, received type {type(others)}")
                super().update(patterns)

__all__ = ["MaskingPattern", "KeyMaskingPattern", "StringMaskingPattern", "MaskingPatternSet"]
