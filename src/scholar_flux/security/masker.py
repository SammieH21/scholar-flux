# /security/masker.py
"""The scholar_flux.security.masker defines the SensitiveDataMasker that is used during API retrieval and processing.

The SensitiveDataMasker implements the logic necessary to determine text strings to mask and is used to identify and
mask potentially sensitive fields based on dictionary fields and string-based patterns.

This class is also used during initialization and within the scholar_flux.SearchAPI class to identify and mask API keys,
emails, and other forms of sensitive data with the aim of redacting text from both console and file system logs.

"""
from typing import List, Optional, Set, Any, MutableSequence
from pydantic import SecretStr
from scholar_flux.security.patterns import (
    MaskingPattern,
    MaskingPatternSet,
    KeyMaskingPattern,
    FuzzyKeyMaskingPattern,
    StringMaskingPattern,
)
from scholar_flux.security.utils import SecretUtils
from scholar_flux.utils.repr_utils import generate_repr


class SensitiveDataMasker:
    """The main interface used by the scholar_flux API for masking all text identified as sensitive.

    This class is used by scholar_flux to ensure that all sensitive text sent to the scholar_flux.logger is masked.

    The SensitiveDataMasker operates through the registration of patterns that identify the text to mask.

    Components:
        - **KeyMaskingPattern**:
            identifies specific keys and regex patterns that will signal text to filter
        - **StringMaskingPattern**:
            identifies strings to filter either by fixed or pattern matching
        - **MaskingPatternSet**:
            A customized set accepting only subclasses of MaskingPatterns that specify
            the rules for filtering text of sensitive fields.

    By default, this structure implements masking for email addresses, API keys, bearer tokens, etc.
    that are identified as sensitive parameters/secrets.

    Args:
        register_defaults (bool):
            Determines whether or not to add the patterns that filter API keys email parameters and auth bearers.

    Examples:
        >>> from scholar_flux.security import SensitiveDataMasker # imports the class
        >>> masker = SensitiveDataMasker(register_defaults = True) # initializes a masker with defaults
        >>> masked = masker.mask_text("'API_KEY' = 'This_Should_Be_Masked_1234', email='a.secret.email@address.com'")
        >>> print(masked)
        # Output: "'API_KEY' = '***', email='***'"

        >>> new_secret = "This string should be filtered"
        ### specifies a new secret to filter - uses regex by default
        >>> masker.add_sensitive_string_patterns(name='custom', patterns=new_secret, use_regex = False)
        # applying the filter
        >>> masked = masker.mask_text(f"The following string should be masked: {new_secret}")
        >>> print(masked)
        # Output: "The following string should be masked: ***"

    """

    def __init__(self, register_defaults: bool = True):
        """Initializes the SensitiveDataMasker for registering and applying different masking patterns, each with a name
        and pattern that will be scrubbed from text with the use of the mask_text method.

        Args:
            register_defaults: (bool): Indicates whether to register_defaults for scrubbing emails,
            api_keys, Authorization Bearers, etc. from the  text when applying self.mask_text
        Attributes:
            self.patterns (Set[MaskingPattern]):
                Indicates the full list of patterns that will be applied when scrubbing text of sensitive fields
                using masking patterns.

        """
        self.patterns: set[MaskingPattern] = MaskingPatternSet()

        if register_defaults:
            self._register_api_defaults()

    def add_pattern(self, pattern: MaskingPattern) -> None:
        """Adds a pattern to the self.patterns attribute."""
        self.patterns.add(pattern)

    def update(
        self,
        pattern: (
            MaskingPattern
            | Set[MaskingPattern]
            | Set[KeyMaskingPattern]
            | Set[StringMaskingPattern]
            | MutableSequence[MaskingPattern | KeyMaskingPattern | StringMaskingPattern]
        ),
    ) -> None:
        """Adds a pattern to the self.patterns attribute."""

        pattern_set = {pattern} if not isinstance(pattern, (MutableSequence, set)) else pattern
        self.patterns.update(pattern_set)

    def remove_pattern_by_name(self, name: str) -> int:
        """Remove patterns by name, return count of removed patterns."""
        initial_count = len(self.patterns)
        self.patterns = {p for p in self.patterns if p.name != name}
        return initial_count - len(self.patterns)

    def get_patterns_by_name(self, name: str) -> Set[MaskingPattern]:
        """Get all patterns with a specific name."""
        return {p for p in self.patterns if p.name == name}

    def add_sensitive_key_patterns(self, name: str, fields: List[str] | str, fuzzy: bool = False, **kwargs) -> None:
        """Adds patterns that identify potentially sensitive strings with the aim of filtering them from logs.

        The parameters provided to the method are used to create new string patterns.

        Args:
            name (str):
                The name associated with the pattern (aides identification of patterns)
            fields (List[str] | str):
                The list of fields to identify to search and remove from logs.
            pattern (str):
                An optional parameter for filtering and removing sensitive fields that match a given pattern.
                By default this is already set to remove api keys that are typically denoted by alpha numeric fields
            fuzzy (bool): If true, regular expressions are used to identify keys. Otherwise the fixed (field) key
                          matching is used through the implementation of a basic KeyMaskingPattern.
            **kwargs:
                Other fields, specifiable via additional keyword arguments that are passed to KeyMaskingPattern

        """

        if isinstance(fields, str):
            fields = [fields]

        Pattern = KeyMaskingPattern if not fuzzy else FuzzyKeyMaskingPattern

        for field in fields:
            pattern = Pattern(name=name, field=field, **kwargs)
            self.add_pattern(pattern)

    def add_sensitive_string_patterns(self, name: str, patterns: List[str] | str, **kwargs) -> None:
        """Adds patterns that identify potentially sensitive strings with the aim of filtering them from logs.

        The parameters provided to the method are used to create new string patterns
        Args:
            name (str): The name associated with the pattern (aides identification of patterns)
            patterns (List[str] | str): The list of patterns to search for and remove from logs
            **kwargs:
                Other fields, specifiable via additional keyword arguments that are passed to StringMaskingPattern

        """
        if isinstance(patterns, str):
            patterns = [patterns]

        for pattern in patterns:
            mask_pattern = StringMaskingPattern(name=name, pattern=pattern, **kwargs)
            self.add_pattern(mask_pattern)

    def register_secret_if_exists(
        self,
        field: str,
        value: SecretStr | Any,
        name: Optional[str] = None,
        use_regex: bool = False,
        ignore_case: bool = True,
    ) -> bool:
        """Identifies fields already registered as secret strings and adds a relevant pattern for ensuring that the
        field, when unmasked for later use, doesn't display in logs. Note that if the current field is not a SecretStr,
        the method will return False without modification or side-effects.

        The parameters provided to the method are used to create new string patterns
        when a SecretStr is detected.

        Args:
            field (str):
                The field, parameter, or key associated with the secret key
            value (SecretStr | Any):
                The value, if typed as a secret string, to be registered as a pattern
            name (Optional[str]):
                The name to add to identify the relevant pattern by within the pattern set. If not provided, defaults
                to the field name.
            use_regex (bool):
                Indicates whether the current function should use regular expressions when matching the pattern in text.
                Defaults to False.
            ignore_case (bool):
                Whether we should consider case when determining whether or not to filter a string. Defaults to True.

        Returns:
            bool:
                If the value is a SecretStr, a string masking pattern is registered for the value and True is returned.
                if the value is not a SecretStr, False is returned and no side-effects will occur in this case.

        Example:
            >>> masker = SensitiveDataMasker()
            >>> api_key = SecretStr("sk-123456")
            >>> registered = masker.register_secret_if_exists("api_key", api_key)
            >>> print(registered)  # True
            >>> registered = masker.register_secret_if_exists("normal_field", "normal_value")
            >>> print(registered)  # False

        """
        if self.is_secret(value):
            mask_pattern = StringMaskingPattern(
                name=name or field,
                pattern=value,
                use_regex=use_regex,
                ignore_case=ignore_case,
            )
            self.add_pattern(mask_pattern)
            return True
        return False

    def _register_api_defaults(self) -> None:
        """Contains the default fields that will be used to remove sensitive strings and parameters such as API keys,
        emails, etc. from text/logs.

        When ran, this method updates the `self.patterns` attribute with default patterns for scrubbing the console text
        and logs of email regex pattern matches, authorization bearer headers, and API keys that could otherwise appear
        in json structures if unaccounted for.

        """
        self.add_sensitive_key_patterns(
            name="api_key",
            fields=["api_key", "apikey", "API_KEY", "APIKEY"],
            pattern=r"[A-Za-z0-9\-_]+",
        )
        self.add_sensitive_key_patterns(
            name="emails",
            fields=["[eE]?mail", "[E]?MAIL", "mailto", "MAILTO"],
            pattern=r"[a-zA-Z0-9._%+-]+(@|%40)[a-zA-Z0-9.-]+\.[a-zA-Z]+",
            fuzzy=True,
        )
        self.add_sensitive_string_patterns(
            name="auth_headers",
            patterns=[r"[Aa]uthorization\s*:\s*[Bb]earer\s+[A-Za-z0-9\-_]+"],
            replacement="Authorization: Bearer ***",
        )

    def mask_text(self, text: str) -> str:
        """Public method for removing sensitive data from text/logs Note that the data that is obfuscated is dependent
        on what patterns were already previously defined in the SensitiveDataMasker. by default, this includes API keys,
        emails, and auth headers.

        Args:
            text (str): the text to scrub of sensitive data
        Returns:
            the cleaned text that excludes sensitive fields

        """
        if not isinstance(text, str):
            return text
        result = SecretUtils.unmask_secret(text)
        for pattern in self.patterns:
            result = pattern.apply_masking(result)
        return result

    def clear(self) -> None:
        """Clears the `SensitiveDataMasker.patterns` set of all previously registered MaskingPatterns including those
        that were registered by default.

        The masker would otherwise use the available `patterns` set to determine what text strings would be masked when
        the `mask_text` method is called. Calling `mask_text` after clearing all MaskingPatterns from the current masker
        will leave all text unmasked and return the inputted text as is.

        """
        self.patterns.clear()

    @staticmethod
    def mask_secret(obj: Any) -> Optional[SecretStr]:
        """Method for ensuring that any non-secret keys will be masked as secrets.

        Args:
            obj (Any): An object to attempt to unmask if it is a secret string
        Returns:
            obj (SecretStr): A SecretStr representation of the original object

        """
        return SecretUtils.mask_secret(obj)

    @staticmethod
    def unmask_secret(obj: Any) -> Any:
        """Method for ensuring that usable values can be successfully extracted from objects. If the current value is a
        secret string, this method will return the secret value from the object.

        Args:
            obj (Any): An object to attempt to unmask if it is a secret string
        Returns:
            obj (Any): The object's original type before being converted into a secret string

        """
        return SecretUtils.unmask_secret(obj)

    @classmethod
    def is_secret(cls, obj: Any) -> bool:
        """Utility method for verifying whether the current value is a secret. This method delegates the verification of
        the value type to the `SecretUtils` helper class to abstract the implementation details in cases where the
        implementation details might require modification in the future for special cases.

        Args:
            obj (Any): The object to check

        Returns:
            bool: True if the object is a SecretStr, False otherwise

        """
        return SecretUtils.is_secret(obj)

    def structure(self, flatten: bool = False, show_value_attributes: bool = False) -> str:
        """Helper method for creating an in-memory cache without overloading the representation with the specifics of
        what is being cached.

        By default, nested MaskingPatterns will not be shown.

        """
        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Helper method for creating a string representation of the SensitiveDataMasker in an easy to read manner."""
        return self.structure()


__all__ = ["SensitiveDataMasker"]
