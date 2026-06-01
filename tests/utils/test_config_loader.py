import pytest
from pydantic import SecretStr, ValidationError, TypeAdapter
from dotenv import dotenv_values

from scholar_flux.utils.config_loader import ConfigLoader
from scholar_flux.utils.settings_utils import SettingsDict, SettingsDictType
from scholar_flux.security import SensitiveDataMasker
from scholar_flux.package_metadata import get_default_writable_directory
from pathlib import Path
import os
import re


@pytest.fixture(autouse=True)
def temp_env_writable_directory(cleanup, tmp_path, monkeypatch):
    """Helper fixture for modifying the default write location when testing the ConfigLoader."""
    monkeypatch.setattr(
        "scholar_flux.package_metadata.get_default_writable_directory", lambda *args, **kwargs: tmp_path
    )


@pytest.fixture
def temp_env_file(cleanup, tmp_path):
    """Uses a temporary environment path variable to setup subsequent config tests."""
    env_path = tmp_path / ".env"
    yield env_path


def test_config_loader_initialization(temp_env_file):
    """Verifies whether the configuration path is set as intended when provided."""
    loader = ConfigLoader(temp_env_file)
    assert loader.env_path == temp_env_file

    non_existent_env_file = temp_env_file / "non-existent-directory" / "b"
    loader = ConfigLoader(non_existent_env_file)
    assert (
        loader.env_path != non_existent_env_file
        and loader.env_path == get_default_writable_directory(directory_type="env") / ".env"
    )

    with pytest.raises(FileNotFoundError):
        _ = ConfigLoader(non_existent_env_file, raise_on_error=True)


def test_write_key_with_masked_and_unmasked_values(cleanup, temp_env_file):
    """Validates whether writing an API key with masking and unmasking works as intended and is triggered by
    keywords."""
    loader = ConfigLoader(env_path=temp_env_file)
    assert loader.env_path == temp_env_file
    key = "CONF_TEST_API_KEY"
    value = "supersecretvalue123"

    # Write masked value (simulate as SecretStr)
    masked_value = SecretStr(value)
    loader.write_key(key, masked_value.get_secret_value(), env_path=temp_env_file)

    # Read back and check - the value will be masked since it contains API_KEY
    loader.load_config(env_path=temp_env_file, reload_env=True)
    assert loader.config[key] == masked_value

    # Overwrite with unmasked value
    loader.write_key(key, value, env_path=temp_env_file)
    env_vars2 = dotenv_values(temp_env_file)
    assert env_vars2[key] == value


def test_plaintext_conversion_with_none_or_empty_strings():
    """Verifies that passing `None` or empty strings to ConfigLoader._to_plaintext() will return an empty string."""
    assert ConfigLoader._to_plaintext("") == ""
    assert ConfigLoader._to_plaintext(SecretStr("")) == ""
    assert ConfigLoader._to_plaintext(None) == ""
    assert ConfigLoader._to_plaintext(SecretStr(None)) == ""  # type: ignore


def test_write_key_with_masked_secret(cleanup, temp_env_file):
    """Verifies that writing secret settings to the env correctly masks when stored, converting when written to .env."""
    loader = ConfigLoader(env_path=temp_env_file)
    assert loader.env_path == temp_env_file
    key = "A_BYTE_ENCODED_SECRET_KEY_ENV_VAR"
    value = b"anothersupersecretvalue123"

    # Generally, bytes aren't stored directly as SecretStr, but they're compatible with the class
    loader.set(key, SensitiveDataMasker.mask_secret(value, convert_object=False))

    # Verify that the key is still identical to the original value
    retrieved = loader.get(key)
    assert SensitiveDataMasker.is_secret(retrieved) and value == SensitiveDataMasker.unmask_secret(retrieved)

    # Should unmask the secret key and convert it into a string internally
    loader.write_key(key, env_path=temp_env_file)

    another_loader = ConfigLoader(temp_env_file)
    another_loader.load_config(reload_env=True)

    value_from_env = another_loader.get(key)
    assert SensitiveDataMasker.is_secret(value_from_env)
    # Values are converted before being re-read
    assert value.decode() == SensitiveDataMasker.unmask_secret(value_from_env)


def test_write_nonexistent_key(cleanup, temp_env_file, caplog):
    """Verifies that attempting to write a nonexistent key raises a KeyError by default."""
    loader = ConfigLoader(env_path=temp_env_file)
    missing_key_name = "nonexistent_key"

    err = re.escape(
        f"Failed to store the configuration setting, '{missing_key_name}', within {temp_env_file}: The key does not "
        "exist within the configuration settings."
    )

    with pytest.raises(KeyError, match=err):
        loader.write_key(missing_key_name, env_path=temp_env_file)  # Default raises

    assert re.search(err, caplog.text) is not None
    caplog.clear()

    loader.write_key(missing_key_name, env_path=temp_env_file, raise_on_error=False)  # Gracefully continue
    assert re.search(err, caplog.text) is not None


def test_config_saving_equivalence(cleanup, tmp_path):
    """Validates whether the creation of a new env file on `self.write_key` is successful when not already created."""
    env_path = tmp_path / ".env"
    loader = ConfigLoader(env_path=env_path)
    assert not env_path.exists()

    key = "CONF_TWO_TEST_API_KEY"
    value = "supersecretvalue123"
    loader.config[key] = SensitiveDataMasker.mask_secret(value)

    loader.save_config()
    assert env_path.exists()
    new_loader = ConfigLoader(env_path=env_path)
    new_loader.load_config(reload_env=True)
    assert new_loader.config == loader.config


def test_unset_config(monkeypatch, caplog):
    """Tests `config_loader.unset()` when an environment variable exists ."""
    new_loader = ConfigLoader()
    env_var = "SCHOLAR_FLUX_DUMMY_VAR"
    value = "11"
    success_msg = f"Removed the variable, {env_var}, from the environment."
    fail_msg = f"The environment variable, {env_var} could not be found within the `ConfigLoader`. Skipping removal..."

    with monkeypatch.context() as m:
        m.setenv(env_var, value)
        new_loader.set(env_var, value)
        assert new_loader.unset(env_var, verbose=True)  # value should be removed
        assert os.getenv(env_var)  # not removed unless unset_os_env
        assert success_msg in caplog.text
        caplog.clear()

        # When unset_os_env is False, the environment is left unmodified
        assert not new_loader.unset(env_var, unset_os_env=False)
        assert fail_msg in caplog.text
        caplog.clear()

        # deletes the os env variable for the current session
        assert new_loader.unset(env_var, unset_os_env=True)
        assert success_msg in caplog.text
        caplog.clear()

        # should already be removed from the `ConfigLoader` and OS environment
        assert not new_loader.unset(env_var, unset_os_env=True)
        assert fail_msg in caplog.text


@pytest.mark.parametrize(
    ("key", "mock_value"),
    (
        ("SECRET_TOKEN", "123456789"),
        ("A_RANDOM_API_KEY", "53210___"),
        ("SCHOLAR_FLUX_DEFAULT_MAILTO", "a.valid@mail.com"),
    ),
)
def test_config_sensitive_string_masking_roundtrip(key, mock_value, caplog):
    """Verifies that sensitive values (emails, tokens, API keys) are masked when storing and retrieving from config."""
    loader = ConfigLoader()

    masked_value = SensitiveDataMasker.mask_secret(mock_value)

    # Assume that the pydantic.SecretStr is already present within the config - setup
    loader.config[key] = masked_value

    # Retrieve the masked value - should remain a secret. Use `SensitiveDataMasker.unmask_secret` to unmask if masked
    assert masked_value == loader.get(key)

    # Set the unmasked value - should mask on storage if unmasked
    loader.set(key, mock_value, verbose=True)
    # When retrieved, the value should still be masked
    assert loader.get(key) == masked_value
    # Verify that the previous value was the overwritten and logged
    assert f"Overwriting configuration setting: {key}" in caplog.text


def test_process_env_resolves_env_with_prefix(tmp_path):
    """Verifies that .env files resolve when prefixed with a name."""
    env_path = Path(tmp_path) / "env_file_with_a_name.env"
    resolved_env_path = ConfigLoader.process_env_path(env_path)
    assert resolved_env_path


def test_write_key_creates_env_file_if_missing(cleanup, tmp_path):
    """Validates whether the creation of a new env file on `self.write_key` is successful when not already created."""
    env_path = tmp_path / ".env"
    loader = ConfigLoader(env_path=env_path)
    key = "CONF_THREE_KEY"
    value = "newvalue"
    assert not env_path.exists()
    loader.write_key(key, value, env_path=env_path)
    assert loader.try_loadenv(env_path)
    env_vars = dotenv_values(env_path)
    assert env_vars[key]


def test_env_key_loader(monkeypatch):
    """Tests whether environment variables can be safely loaded as secret strings when using `load_os_env_key`"""
    api_key_variable_name = "MY_VERY_SECRET_API_KEY"
    api_key = "this_is_my_api_key_1234"
    monkeypatch.setenv(api_key_variable_name, api_key)

    loaded_key = ConfigLoader.load_os_env_key(api_key_variable_name)
    assert isinstance(loaded_key, SecretStr) and loaded_key.get_secret_value() == api_key

    # should work as intended and return nothing
    assert ConfigLoader.load_os_env_key("") is None

    # default error expected when using os.environ.get under the hood
    with pytest.raises(TypeError):
        ConfigLoader.load_os_env_key(None)  # type: ignore


def test_write_key_on_error(cleanup, tmp_path, monkeypatch, caplog):
    """Validates whether creating/writing a new .env file on `self.write_key` will handle errors gracefully."""
    env_path = tmp_path / ".env"

    e = "Some error occurred during file-write for whatever reason..."
    import scholar_flux.utils.config_loader

    monkeypatch.setattr(
        scholar_flux.utils.config_loader, "set_key", lambda *args, **kwargs: (_ for _ in ()).throw(IOError(e))
    )

    loader = ConfigLoader(env_path=env_path)
    key = "CONF_FOUR_NEW_KEY"
    value = "newvalue"

    loader.write_key(key, value, env_path=env_path)
    assert f"Failed to create .env file at {env_path}: {e}" in caplog.text


def test_config_dict_assignment_validation():
    """Verifies that the underlying `ConfigDict` data structure appropriately gates key assignments."""
    new_loader = ConfigLoader()
    assert isinstance(new_loader.config, SettingsDict)

    bad_key = 123
    err = f"The key provided to the SettingsDict is invalid. Expected a str, but received {type(bad_key)}"
    with pytest.raises(TypeError) as excinfo:
        assert new_loader.set(bad_key, False)  # type: ignore

    assert err in str(excinfo.value)

    key = "THIS_IS_AN_APPROPRIATE_ASSIGNMENT"
    new_loader.set(key, True)  # type: ignore
    assert new_loader.get(key) is new_loader.config.get(key)


@pytest.mark.parametrize("invalid_value", ([1, 2, 3], {"a", "bc"}, "3", 2, (1,)))
def test_config_settings_dict_validation_with_invalid_types(invalid_value, caplog):
    """Verifies that the `ConfigDict` appropriately validates incoming inputs that are not dictionaries."""
    err = f"Expected a valid settings dictionary, but received type {type(invalid_value).__name__}"
    assert SettingsDict.is_settings_like(invalid_value) is False

    with pytest.raises(TypeError, match=re.escape(err)):
        _ = SettingsDict.validate_settings_dict(invalid_value)
    assert err in caplog.text

    adapter: TypeAdapter[SettingsDictType] = TypeAdapter(SettingsDictType)
    with pytest.raises(TypeError, match=re.escape(err)):
        _ = adapter.validate_python(invalid_value)


def test_config_settings_dict_validation_with_invalid_keys(caplog):
    """Verifies that the `ConfigDict` appropriately validates incoming keys with invalid types."""
    invalid_dict = {"a": 1, "b": "2", 3: "3"}
    err = "Expected a valid settings dictionary, but at least one field is not a string."

    assert SettingsDict.is_settings_like(invalid_dict) is False
    assert err not in caplog.text  # log only when enabled, False by default

    with pytest.raises(ValueError, match=re.escape(err)):
        _ = SettingsDict.validate_settings_dict(invalid_dict)  # type: ignore
    assert err in caplog.text

    adapter: TypeAdapter[SettingsDictType] = TypeAdapter(SettingsDictType)

    with pytest.raises(ValidationError, match=f".*{re.escape(err)}.*"):
        adapter.validate_python(invalid_dict)  # type: ignore


def test_config_settings_dict_revalidation_equivalence():
    """Verifies that converting a SettingsDict round trip from dict to SettingsDict produces the expected type."""
    adapter: TypeAdapter[SettingsDictType] = TypeAdapter(SettingsDictType)

    new_loader = ConfigLoader()
    assert SettingsDict.is_settings_like(new_loader.config.data)  #  should be convertible

    revalidated_dict = SettingsDict(adapter.validate_python(new_loader.config.data))
    assert isinstance(revalidated_dict, SettingsDict)
    assert revalidated_dict == new_loader.config
