"""The scholar_flux.security module contains classes and models created specifically for ensuring that console and file
logs do not contain sensitive data. The set of modules uses pattern matching to determine whether, when sending a
request, any known API keys are filtered from the logs.

Core classes:
    - SecretUtils: Class with basic static methods for masking and unmasking non-missing strings with pydantic.SecretStr
    - MaskingPattern: Basic pattern from which all subclasses inherit from in order to define rules for masking strings
    - KeyMaskingPattern: Matches key-value pairs for commonly sensitive fixed string fields (e.g. api_key, mailto)
    - FuzzyKeyMaskingPattern: Extends the KeyMaskingPattern for fuzzy field matching when parameter names may vary
    - StringMaskingPattern: Identifies and masks known sensitive strings using either regex or fixed string matching
    - MaskingFilter: Defines the core logging filter used by the dedicated scholar_flux.logger to hide sensitive info
    - MaskingPatternSet: Container that will hold a set of all String- and Key-based patterns used in the package
    - SensitiveDataMasker: Main entry point for managing/adding to/deleting from the list of all patterns to be filtered

Note that the global package level SensitiveDataMasker is instantiated on package loading and can be imported:
    >>> from scholar_flux import masker
    >>> print(masker) # view all currently masked strings and keys
    # Output: "SensitiveDataMasker(patterns=MaskingPatternSet(...))"
    # set up and remove all matching email-like strings
    >>> email_pattern = r"[a-zA-Z0-9._%+-]+(@|%40)[a-zA-Z0-9.-]+[.][a-zA-Z]+"
    >>> masker.add_sensitive_string_patterns( name="email_strings", patterns=email_pattern, use_regex = True)
    >>> masker.mask_text("here_is_my_fake123@email.com")
    # Output: "***"

"""

from scholar_flux.security.utils import SecretUtils
from scholar_flux.security.patterns import (
    MaskingPattern,
    KeyMaskingPattern,
    FuzzyKeyMaskingPattern,
    StringMaskingPattern,
    MaskingPatternSet,
)
from scholar_flux.security.masker import SensitiveDataMasker
from scholar_flux.security.filters import MaskingFilter


__all__ = [
    "SecretUtils",
    "MaskingPattern",
    "KeyMaskingPattern",
    "FuzzyKeyMaskingPattern",
    "StringMaskingPattern",
    "MaskingPatternSet",
    "SensitiveDataMasker",
    "MaskingFilter",
]
