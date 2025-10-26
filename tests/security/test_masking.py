import pytest
from pydantic import SecretStr
import json
from scholar_flux.security import (
    MaskingPattern,
    MaskingPatternSet,
    KeyMaskingPattern,
    FuzzyKeyMaskingPattern,
    StringMaskingPattern,
    SensitiveDataMasker,
)


def test_initialization():
    """Verifies that the sensitive data masker is populated with masking defaults only if `register_defaults=True."""
    masker = SensitiveDataMasker(register_defaults=True)
    assert masker.patterns

    masker = SensitiveDataMasker(register_defaults=False)
    assert not masker.patterns


def test_basic_string_pattern():
    """Verifies that basic string patterns can be redacted by defining the masking pattern with associated options."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    password = "paxw0rD"
    string_pattern = StringMaskingPattern(name="birthdate", pattern=password, replacement=masking_text, use_regex=False)
    masker.add_pattern(string_pattern)

    assert masker.mask_text(password) == masking_text
    string = f"My password is {password}. Please keep this secure"
    masked_string = string.replace(password, masking_text)
    assert masker.mask_text(string) == masked_string


def test_regex_string_pattern():
    """Verifies that regular expressions can be masked from text using regular expressions to identify text to mask."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    string_pattern = StringMaskingPattern(name="birthdate", pattern=r"\d\d\d\d-\d\d-\d\d", replacement=masking_text)
    masker.add_pattern(string_pattern)

    birthdate = "1863-05-25"
    assert masker.mask_text(birthdate) == masking_text
    string = f"He was born in {birthdate} on a sunny day"
    masked_string = string.replace(birthdate, masking_text)
    assert masker.mask_text(string) == masked_string


def test_split_pattern_with_escaped_pipe():
    """Verifies that pattern splitting is only performed when pipes in patterns are not escaped."""
    pattern = r"a|b\|c"
    expected_split_pattern = ["a", r"b\|c"]
    assert expected_split_pattern == KeyMaskingPattern._split_pattern(pattern)

    pattern_two = r"|_/\|_|op"
    expected_split_pattern_two = ["", r"_/\|_", "op"]
    assert expected_split_pattern_two == KeyMaskingPattern._split_pattern(pattern_two)

    pattern_three = "generic_field"
    assert [pattern_three] == KeyMaskingPattern._split_pattern(pattern_three)


def test_fuzzy_key_pattern():
    """Verifies that fuzzy field matching can be performed to mask unknown, fuzzy fields before entry."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    fuzzy_field_pattern = "[a-z_]*birth[a-z_]*|dob|[a-z_]*bday[a-z_]*|[a-z_]*born"
    fuzzy_key_pattern = FuzzyKeyMaskingPattern(
        name="birthdate", field=fuzzy_field_pattern, pattern=r"\d\d\d\d-\d\d-\d\d", replacement=masking_text
    )
    masker.add_pattern(fuzzy_key_pattern)

    birthday_keys = ["birthday", "birth", "date_of_birth", "dob", "my_dob", "my_bday", "date_born"]
    test_dictionary = {key: "1122-34-56" for key in birthday_keys}
    birthday_json = json.dumps(test_dictionary)
    masked_json = masker.mask_text(birthday_json)
    loaded_masked_dictionary = json.loads(masked_json)
    assert loaded_masked_dictionary == {key: masking_text for key in birthday_keys}


def test_sensitive_key_pattern_type():
    """Verifies that the masker uses fuzzy field matching when `fuzzy=True` and, otherwise, uses a KeyMaskingPattern."""
    masker = SensitiveDataMasker(register_defaults=False)

    masker.add_sensitive_key_patterns(name="test", fields=["test_key1", "test_key2"], fuzzy=True)
    assert all(isinstance(pattern, FuzzyKeyMaskingPattern) for pattern in masker.get_patterns_by_name("test"))
    masker.remove_pattern_by_name(name="test")

    masker.add_sensitive_key_patterns(name="test", fields=["test_key1", "test_key2"], fuzzy=False)
    assert all(
        isinstance(pattern, KeyMaskingPattern) and not isinstance(pattern, FuzzyKeyMaskingPattern)
        for pattern in masker.get_patterns_by_name("test")
    )


def test_basic_key_pattern():
    """Validates that key-value pairs that indicate patterns to mask will successfully trigger when encountering strings
    containing the matching pattern."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    birthdate = r"[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?|[0-9][0-9]?-[0-9][0-9]?-[0-9][0-9][0-9][0-9]"
    fields = ["dob", "birthdate", "birthday"]
    string_patterns = {
        KeyMaskingPattern(name="birthdate", field=field, pattern=birthdate, replacement=masking_text)
        for field in fields
    }
    masker.update(string_patterns)
    masked_parameters = json.dumps({field: masking_text for field in fields}).strip()
    parameters = json.dumps({field: "5-12-2024" for field in fields})
    parameters2 = json.dumps({field: "2024-05-12" for field in fields})

    assert masker.mask_text(parameters) == masked_parameters
    assert masker.mask_text(parameters2) == masked_parameters

    # testing selective filtering, only the last should be when regex turned off
    parameters3 = json.dumps(dict(zip(fields, ("aaaaa", "abcde", "ab.*e"))))
    parameters_masked3 = json.dumps(dict(zip(fields, ("aaaaa", "abcde", "***"))))

    masker.add_sensitive_key_patterns(name="no_regex", fields=fields, pattern="ab.*e", use_regex=False)

    assert masker.mask_text(parameters3) == parameters_masked3


def test_pattern_removal():
    """Validates whether patterns can be removed as intended by the name associated with the pattern."""
    masker = SensitiveDataMasker(register_defaults=True)
    assert masker.get_patterns_by_name("api_key") is not None
    masker.remove_pattern_by_name("api_key")
    assert not masker.get_patterns_by_name("api_key")


def test_factory_key_patterns():
    """Validates whether key patterns can be initialized without defining the underlying KeyMaskingPattern upfront."""
    masker = SensitiveDataMasker(register_defaults=False)

    # lists and strings should work in this scenario:
    masker.add_sensitive_key_patterns(name="api_key", fields=["api_key"])
    masker.add_sensitive_key_patterns(name="api_key", fields="API_KEY")

    string = '{"api_key": "abcd1234", "API_KEY": "abcd5432"}'
    masked_string = '{"api_key": "***", "API_KEY": "***"}'
    assert masker.mask_text(string) == masked_string

    masker.add_sensitive_string_patterns(name="string_match", patterns="[pP][aA][sS][sS](:|=) *1234")

    assert masker.mask_text("here is my password: pass: 1234") == "here is my password: ***"


def test_secret_masking():
    """Ensures that secrets can be masked and unmasked when required based on whether or not the key is already a secret
    string.

    When non-secrets are entered into `unmask_secret`, they should be returned as is.

    Conversely, with `mask_secret`, non-secrets, unless None, should be coerced into secrets if not already a secret.
    Otherwise, secrets should be returned as is.

    The `register_secret_if_exists` method is also tested and expected to work similarly:
        With a secret as input, the value of the secret will be added as a masked text patterns and return True.
        Otherwise, no patterns are added, and False is returned to signify that nothing was added.

    """
    masker = SensitiveDataMasker(register_defaults=False)
    assert masker.mask_secret(None) is None
    assert masker.mask_secret("") == SecretStr("")
    assert masker.unmask_secret(masker.mask_secret("")) == masker.unmask_secret(SecretStr(""))
    assert masker.unmask_secret(None) is None

    a_secret = SecretStr("plaintext_password")
    a_non_secret = "plaintext_info"

    assert not masker.register_secret_if_exists(field="another_secret", value=a_non_secret, name="non_secret")
    assert not masker.get_patterns_by_name("non_secret")

    assert masker.register_secret_if_exists(field="a_secret", value=a_secret, name="new_secret")
    new_secret = list(masker.get_patterns_by_name("new_secret"))
    assert new_secret and isinstance(new_secret[0].pattern, SecretStr) and new_secret[0].pattern == a_secret

    masker.add_sensitive_string_patterns(name="new_secret", patterns=[a_secret.get_secret_value()], use_regex=False)

    assert masker.mask_text(None) is None and masker.mask_text(1) == 1  # type:ignore


def test_repr():
    """Verifies that the patterns shown in the SensitiveDataMasker's representation are masked and not directly
    shown."""
    masker = SensitiveDataMasker(register_defaults=True)
    assert repr(masker) == "SensitiveDataMasker(patterns=MaskingPatternSet(...))"

    # when no patterns are added, the `...` won't be present
    masker = SensitiveDataMasker(register_defaults=False)
    assert repr(masker) == "SensitiveDataMasker(patterns=MaskingPatternSet())"


def test_masking_pattern_abc():
    """Tests the underlying MaskingPattern parent class to verify the implementation of the underlying methods used to
    compare patterns, hashes, and `_identity_key` methods."""
    string_pattern = StringMaskingPattern(name="abstract testing", pattern="abc")
    key_pattern = KeyMaskingPattern(name="abstract testing", field="subclassing", pattern="abc")

    assert MaskingPattern.apply_masking(string_pattern, "placeholder") is None
    assert isinstance(MaskingPattern.__hash__(string_pattern), int)
    assert MaskingPattern.__eq__(string_pattern, string_pattern) is True
    assert MaskingPattern.__eq__(string_pattern, 1) is False
    assert MaskingPattern.__eq__(string_pattern, key_pattern) is False
    assert MaskingPattern._identity_key(string_pattern) is None


def test_pattern_identity():
    """Validates whether the identity_key correctly identifies StringMaskingPatterns and KeyMaskingPatterns based on
    their respective configuration.

    StringMaskingPatterns should be identifiable based their assigned names and the secret values of their patterns.

    KeyMaskingPatterns should be identifiable based on the name assigned to a pattern, the associated field (or key)
    indicating the pattern to mask, and the secret values of their patterns.

    """
    string_pattern = StringMaskingPattern(name="abstract testing", pattern="abc")
    key_pattern = KeyMaskingPattern(name="key_patterns", field="identity", pattern="abc")
    assert string_pattern._identity_key() == f"('StringMaskingPattern', '{string_pattern.name}', '{string_pattern.pattern.get_secret_value()}')"  # type: ignore
    assert key_pattern._identity_key() == f"('KeyMaskingPattern', '{key_pattern.name}', '{key_pattern.field}', '{key_pattern.pattern.get_secret_value()}')"  # type: ignore


def test_pattern_set():
    """Validates whether, as intended, the `MaskingPatternSet` will correctly allow only patterns and otherwise raise a
    type error when encountering incorrect types."""
    string_pattern = StringMaskingPattern(name="abstract testing", pattern="abc")
    key_pattern = KeyMaskingPattern(name="key_patterns", field="identity", pattern="abc")
    pattern_set = MaskingPatternSet()

    pattern_set.add(key_pattern)
    pattern_set.update(string_pattern)  # type: ignore
    assert string_pattern in pattern_set

    item = 1
    with pytest.raises(TypeError) as excinfo:
        pattern_set.add(item)  # type: ignore
    assert f"Expected a MaskingPattern, got {type(item)}" in str(excinfo.value)

    item_tuple = (2,)
    with pytest.raises(TypeError) as excinfo:
        pattern_set.update((item_tuple,))  # type: ignore
    assert f"Expected a masking pattern, received type {type(item_tuple)}" in str(excinfo.value)
