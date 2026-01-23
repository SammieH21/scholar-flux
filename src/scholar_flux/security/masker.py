# /security/masker.py
"""The scholar_flux.security.masker defines the SensitiveDataMasker that is used during API retrieval and processing.

The SensitiveDataMasker implements the logic necessary to determine text strings to mask and is used to identify and
mask potentially sensitive fields based on dictionary fields and string-based patterns.

This class is also used during initialization and within the scholar_flux.SearchAPI class to identify and mask API keys,
emails, and other forms of sensitive data with the aim of redacting text from both console and file system logs.

"""
from typing import List, Optional, Set, Any, MutableSequence, Callable, TypeVar, ParamSpec
from collections import deque
from pydantic import SecretStr, BaseModel
from dataclasses import is_dataclass
from scholar_flux.security.patterns import (
    MaskingPattern,
    MaskingPatternSet,
    KeyMaskingPattern,
    FuzzyKeyMaskingPattern,
    StringMaskingPattern,
)
from scholar_flux.security.utils import SecretUtils
from scholar_flux.utils.repr_utils import generate_repr
from functools import wraps

P = ParamSpec("P")
R = TypeVar("R")


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
        # OUTPUT: 'API_KEY' = '***', email='***'

        # specifying a new secret to filter: uses regex by default
        >>> new_secret = "This string should be filtered"
        >>> masker.add_sensitive_string_patterns(name='custom', patterns=new_secret, use_regex = False)

        # applying the filter
        >>> masked = masker.mask_text(f"The following string should be masked: {new_secret}")
        >>> print(masked)
        # OUTPUT: The following string should be masked: ***

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
            >>> print(registered)
            # OUTPUT: True
            >>> registered = masker.register_secret_if_exists("normal_field", "normal_value")
            >>> print(registered)
            # OUTPUT: False

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
            fields=["api_key", "apikey", "secret_key", "secretkey", "fernetkey", "fernet_key"],
            pattern=r"[A-Za-z0-9\-_]+",
            ignore_case=True,
            apply_to_dict=True,
        )
        self.add_sensitive_key_patterns(
            name="emails",
            fields=["mail", "email", "mailto"],
            pattern=r"[a-zA-Z0-9._%+-]+(@|%40)[a-zA-Z0-9.-]+\.[a-zA-Z]+",
            ignore_case=True,
            fuzzy=True,
            apply_to_dict=True,
        )
        # Password fields - TWO patterns needed:
        # 1. KeyMaskingPattern (dict-only): for actual dict objects
        #    Dict-only because "pass" would cause false positives in text ("pass the test")
        self.add_sensitive_key_patterns(
            name="password_fields_dict",
            fields=["password", "pass", "passwd", "pwd"],
            ignore_case=True,
            apply_to_text=False,  # Only mask in dictionaries
            apply_to_dict=True,
        )
        # 2. StringMaskingPattern (text-only): for JSON/repr strings
        #    Matches "password": "value" patterns in stringified configs
        #    Pattern preserves quote structure: "password": "***" or 'password': '***'
        self.add_sensitive_string_patterns(
            name="password_fields_text",
            patterns=[
                # Handles both quoted and unquoted values, preserves quote style
                r"""((?:["']?)(?:password|pass|passwd|pwd)(?:["']?)\s*[:\=]\s*)(["']?)([^"',}\s]+)(["']?)"""
            ],
            replacement=r"\1\2***\4",  # Preserves opening and closing quotes
            ignore_case=True,
            apply_to_text=True,  # Mask in text/JSON
        )
        self.add_sensitive_string_patterns(
            name="SecretStr",
            patterns=[
                # Ensures that SecretStr implementations are masked in the logs (including the SecretStr class name)
                r"""(SecretStr|\*{3})\(["']?\*{10}["']?\)"""
            ],
            replacement="**********",  # for consistency with default str(SecretStr) behavior
            mask_pattern=False,
            apply_to_text=True,  # Mask in text/JSON
        )
        # Database URI passwords (postgresql, postgres, mysql, mariadb, duckdb, redis, mongodb)
        # Pattern breakdown:
        #   Group 1: scheme://user:  (captures everything up to and including the colon before password)
        #   Group 2: password        (greedy .+ captures password, including any @ characters)
        #   Group 3: @host[:port]    (captures @hostname with optional port, regex backtracks to find last valid @host)
        #            Supports both standard host names and bracketed IPv6 addresses (e.g., [::1], [2001:db8::1])
        # Example: postgresql://user:p@ss@host:5432/db → postgresql://user:***@host:5432/db
        # Example: postgresql://user:p@ss@[::1]:5432/db → postgresql://user:***@[::1]:5432/db
        self.add_sensitive_string_patterns(
            name="db_uri_credentials",
            patterns=[
                r"((?:postgres(?:ql)?|mysql|mariadb|duckdb|redis|mongodb(?:\+srv)?)(?:\+\w+)?://[^:@/]*:)(.+)(@(?:\[[a-fA-F0-9:]+\]|[a-zA-Z0-9.-]+)(?::\d+)?)"
            ],
            replacement=r"\1***\3",
        )
        # motherduck tokens in query strings
        self.add_sensitive_string_patterns(
            name="motherduck_tokens",
            patterns=[r"(motherduck_token=)([^&\s\"']+)"],
            replacement=r"\1***",
        )
        # Common secrets in URL query parameters (authentication tokens)
        self.add_sensitive_string_patterns(
            name="url_query_secrets",
            patterns=[r"([?&](?:token|access_token|auth_token|session_token|secret|api_?key|password)=)([^&\s\"']+)"],
            replacement=r"\1***",
        )
        # Private key headers (RSA and encrypted keys - most common types)
        # Catches: "BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "BEGIN ENCRYPTED PRIVATE KEY"
        self.add_sensitive_string_patterns(
            name="private_key_headers",
            patterns=[r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----"],
            replacement="***PRIVATE_KEY_REDACTED***",
            ignore_case=True,
        )
        self.add_sensitive_string_patterns(
            name="auth_headers",
            patterns=[r"authorization\s*:\s*bearer\s+[A-Za-z0-9\-_]+"],
            replacement="Authorization: Bearer ***",
            ignore_case=True,
        )

    def mask_dict(self, data: dict, convert_objects: bool = False) -> dict:
        """Masks sensitive values in dictionaries based on registered key patterns.

        This method provides more reliable masking for structured data than string pattern matching, as it directly
        matches dictionary keys rather than parsing formatted text.

        Args:
            data (dict): The dictionary to mask
            convert_objects (bool): Defines whether to convert data objects (BaseModels, dataclasses) as masked strings

        Returns:
            (dict): New dictionary with sensitive values masked

        Example:
            >>> masker = SensitiveDataMasker()
            >>> config = {'password': 'secret123', 'host': 'localhost'}
            >>> masked = masker.mask_dict(config)
            >>> print(masked)
            # OUTPUT: {'password': '***', 'host': 'localhost'}

        """
        if not isinstance(data, dict):
            return data
        result: dict = {}
        for key, value in data.items():
            replacement = self._get_dict_key_replacement(key) if isinstance(key, str) else None
            if replacement is not None:
                result[key] = replacement
            else:
                result[key] = self.mask_value(value, convert_objects)
        return result

    def mask_list(self, data: list | tuple, convert_objects: bool = False) -> list:
        """Masks sensitive values in lists based on registered patterns.

        Recursively processes nested structures (dicts, lists, tuples) and applies
        masking patterns to any sensitive content found.

        Args:
            data (list | tuple): list or tuple to mask

        Returns:
            list: New list with sensitive values masked

        Note:
            For type-safety, tuples are converted into lists and may need to be converted as a tuple if used as input.

        Example:
            >>> masker = SensitiveDataMasker()
            >>> configs = [{'password': 'secret'}, 'api_key=12345']
            >>> masked = masker.mask_list(configs)
            >>> print(masked)
            # OUTPUT: [{'password': '***'}, 'api_key=***']

        """
        if not isinstance(data, (list, tuple)):
            return data

        return [self.mask_value(item, convert_objects) for item in data]

    def mask_object(self, value: Any) -> Any:
        """Converts objects into their masked string representation.

        Args:
            value (Any): The value to convert and mask

        Returns:
            str: Masked string representation of the value

        """
        if isinstance(value, BaseModel) or is_dataclass(value):
            return self.mask_text(repr(value))
        return self.mask_text(str(value)) if value is not None else value

    def mask_value(self, value: Any, convert_objects: bool = False) -> Any:
        """Recursively masks a single value based on its type."""
        match value:
            case dict():
                return self.mask_dict(value, convert_objects)
            case tuple():
                return tuple(self.mask_value(item, convert_objects) for item in value)
            case set():
                return {self.mask_value(item, convert_objects) for item in value}
            case deque():
                return value.__class__((self.mask_value(item, convert_objects) for item in value), maxlen=value.maxlen)
            case list():
                return self.mask_list(value, convert_objects)
            case str():
                return self.mask_text(value)
            case value if convert_objects:
                return self.mask_object(value)
            case _:
                return value

    def _get_dict_key_replacement(self, key: Any) -> Any:
        """Finds the replacement string for a sensitive dict key.

        If not sensitive, None is returned instead..

        """
        for pattern in self.patterns:
            if isinstance(pattern, KeyMaskingPattern) and pattern.apply_to_dict and pattern.matches_key(key):
                return pattern.replacement
        return None

    def mask_text(self, text: str) -> str:
        """Public method for removing sensitive data from text/logs Note that the data that is obfuscated is dependent
        on what patterns were already previously defined in the SensitiveDataMasker. by default, this includes API keys,
        emails, and auth headers.

        Args:
            text (str): the text to scrub of sensitive data
        Returns:
            str: The cleaned text that excludes sensitive fields

        """
        if not isinstance(text, str):
            return text
        result = SecretUtils.unmask_secret(text)
        for pattern in self.patterns:
            # Skip patterns not configured for text masking
            if not pattern.apply_to_text:
                continue
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

    def mask_output(self, convert_objects: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorator that wraps a function or method using the current SensitiveDataMasker to mask sensitive values.

        Args:
            convert_objects (bool):
                If True, objects of unknown types are converted to strings before masking. Otherwise, no conversion
                takes place, and only strings (passed explicitly or nested within dictionaries, lists, sets) are masked.
                Defaults to False.

        Returns:
            Callable[[Callable[P, R]], Callable[P, R]]:
                A decorator that wraps a function, masking its output according to the registered patterns.

        Note:
            The decorated function's signature and docstring are preserved via ``functools.wraps``.

        Example:
            >>> import os
            >>> from scholar_flux import masker
            >>> @masker.mask_output()
            ... def default_config():
            ...     return {'API_KEY': os.environ.get('EXAMPLE_API_KEY'), 'host': 'https://example-api.com'}
            >>> default_config()
            # OUTPUT: {'API_KEY': '***', 'host': 'https://example-api.com'}

        """

        def decorator(
            fn: Callable[P, R],
        ) -> Callable[P, R]:
            """Decorator defining the function or to method to be wrapped once the object masking logic is set."""

            @wraps(fn)
            def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
                """Wrapper that enables inputs to be masked when a sensitive value is detected."""
                output = fn(*args, **kwargs)
                return self.mask_value(output, convert_objects=convert_objects)

            return wrapped

        return decorator

    def __repr__(self) -> str:
        """Helper method for creating a string representation of the SensitiveDataMasker in an easy to read manner."""
        return self.structure()


__all__ = ["SensitiveDataMasker"]
