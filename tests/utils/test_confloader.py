import os
import pytest
from pathlib import Path
from pydantic import SecretStr
from dotenv import dotenv_values
import dotenv

from scholar_flux.utils.config_loader import ConfigLoader
from scholar_flux.security import SensitiveDataMasker
from scholar_flux.package_metadata import get_default_writable_directory

@pytest.fixture(autouse = True)
def temp_env_writable_directory(cleanup, tmp_path, monkeypatch):
    """Helper fixture for modifying the default write location when testing the ConfigLoader"""
    import scholar_flux.package_metadata.directories
    monkeypatch.setattr(scholar_flux.package_metadata, "get_default_writable_directory", lambda *args, **kwargs: tmp_path)

@pytest.fixture
def temp_env_file(cleanup, tmp_path):
    """Uses a temporary environment path variable to setup subsequent config tests"""
    env_path = tmp_path / ".env"
    yield env_path

def test_process_env_file(temp_env_file):
    """Verifies whether the configuration path is set as intended when provided"""
    loader = ConfigLoader(temp_env_file)
    assert loader.env_path == temp_env_file

    non_existent_env_file = temp_env_file / 'non-existent-directory' / "b"
    loader = ConfigLoader(non_existent_env_file)
    assert loader.env_path != non_existent_env_file and loader.env_path == get_default_writable_directory(directory_type='env') / '.env'

def test_write_key_with_masked_and_unmasked_values(cleanup, temp_env_file):
    """Validates whether writing an API key with masking and unmasking works as intended and is triggered by keywords"""
    loader = ConfigLoader(env_path=temp_env_file)
    assert loader.env_path==temp_env_file
    key = "CONF_TEST_API_KEY"
    value = "supersecretvalue123"

    # Write masked value (simulate as SecretStr)
    masked_value = SecretStr(value)
    loader.write_key(key, masked_value.get_secret_value(), env_path=temp_env_file)

    # Read back and check - the value will be masked since it contains API_KEY
    loader.load_config(env_path=temp_env_file, reload_env = True)
    assert loader.config[key] == masked_value

    # Overwrite with unmasked value
    loader.write_key(key, value, env_path=temp_env_file)
    env_vars2 = dotenv_values(temp_env_file)
    assert env_vars2[key] == value

def test_config_saving_equivalence(cleanup, tmp_path):
    """Validates whether the creation of a new env file on `self.write_key` is successful when not already created"""
    env_path = tmp_path / ".env"
    loader = ConfigLoader(env_path=env_path)
    assert not env_path.exists()

    key = "CONF_TWO_TEST_API_KEY"
    value = "supersecretvalue123"
    loader.config[key] = SensitiveDataMasker.mask_secret(value)

    loader.save_config()
    assert env_path.exists()
    new_loader = ConfigLoader(env_path=env_path)
    new_loader.load_config(reload_env = True)
    assert new_loader.config == loader.config

def test_write_key_creates_env_file_if_missing(cleanup, tmp_path):
    """Validates whether the creation of a new env file on `self.write_key` is successful when not already created"""
    env_path = tmp_path / ".env"
    loader = ConfigLoader(env_path=env_path)
    key = "CONF_THREE_KEY"
    value = "newvalue"
    assert not env_path.exists()
    loader.write_key(key, value, env_path=env_path)
    assert loader.try_loadenv(env_path)
    env_vars = dotenv_values(env_path)
    assert env_vars[key] 


def test_write_key_on_error(cleanup, tmp_path, monkeypatch, caplog):
    """Validates whether expected errors when creating/writing a new env file on `self.write_key` will handle errors gracefully"""
    env_path = tmp_path / ".env"

    e = "Some error occurred during file-write for whatever reason..."
    import scholar_flux.utils.config_loader
    
    monkeypatch.setattr(scholar_flux.utils.config_loader, "set_key", lambda *args, **kwargs: (_ for _ in ()).throw(IOError(e)))

    loader = ConfigLoader(env_path=env_path)
    key = "CONF_FOUR_NEW_KEY"
    value = "newvalue"
    
    loader.write_key(key, value, env_path=env_path)
    assert f"Failed to create .env file at {env_path}: {e}" in caplog.text
