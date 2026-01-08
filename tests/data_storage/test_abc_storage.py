"""Direct ABCStorage tests to cover basic functionality before subclassed overrides."""

import pytest
import copy
from scholar_flux.data_storage.abc_storage import ABCStorage


@pytest.fixture
def patch_abc_storage(monkeypatch):
    """Patch ABCStorage to allow direct instantiation for testing base class methods."""
    monkeypatch.setattr(ABCStorage, "__abstractmethods__", set())


@pytest.fixture()
def abc_storage(patch_abc_storage) -> ABCStorage:
    """Creates a basic ABCStorage bypassing the abstract method checks."""
    return ABCStorage()  # type: ignore


def test_abc_storage_initialization(abc_storage):
    """Test basic initialization of ABCStorage subclass."""
    abc_storage._initialize()  # doesn't do anything - to be subclassed
    assert abc_storage.namespace is None
    assert abc_storage.raise_on_error is False
    assert abc_storage.config == {}
    assert abc_storage.ttl is None


def test_not_implemented_functionality(abc_storage):
    """Verifies that functionality to be subclassed raises a NotImplementedError if not subclassed."""
    NOT_IMPLEMENTED = (
        abc_storage.retrieve,
        abc_storage.retrieve_all,
        abc_storage.retrieve_keys,
        abc_storage.update,
        abc_storage.delete,
        abc_storage.delete_all,
        abc_storage.verify_cache,
        abc_storage.is_available,
        abc_storage.clone,
        abc_storage.verify_connection,
    )
    for storage_method in NOT_IMPLEMENTED:
        with pytest.raises(NotImplementedError):
            storage_method()


def test_get_default_config():
    """Test _get_default_config returns empty dict by default."""
    config = ABCStorage._get_default_config()
    assert isinstance(config, dict)
    assert config == {}


def test_deepcopy_raises_not_implemented(abc_storage):
    """Test that deepcopy raises NotImplementedError."""
    with pytest.raises(NotImplementedError) as excinfo:
        copy.deepcopy(abc_storage)

    assert "ABCStorage cannot be deep-copied" in str(excinfo.value)
    assert "Use the .clone() method" in str(excinfo.value)


def test_prefix_without_namespace(abc_storage):
    """Test _prefix method without namespace."""
    key = "test_key"

    assert abc_storage._prefix(key) == key


def test_ping_no_error(abc_storage):
    """Test _prefix method without namespace."""
    abc_storage.ping()  # shouldn't raise an error on successes
    assert True


def test_prefix_with_namespace(abc_storage):
    """Test _prefix method with namespace."""
    abc_storage.namespace = "TEST"
    key = "test_key"

    assert abc_storage._prefix(key) == "TEST:test_key"


def test_prefix_already_prefixed(abc_storage):
    """Test _prefix method with already prefixed key."""
    abc_storage.namespace = "TEST"
    key = "TEST:test_key"

    # Should not double-prefix
    assert abc_storage._prefix(key) == "TEST:test_key"


def test_prefix_empty_key_raises_error(abc_storage):
    """Test _prefix raises KeyError for empty key."""
    with pytest.raises(KeyError) as excinfo:
        abc_storage._prefix("")

    assert "No valid value provided for key" in str(excinfo.value)


def test_prefix_none_key_raises_error(abc_storage):
    """Test _prefix raises KeyError for None key."""
    with pytest.raises(KeyError) as excinfo:
        abc_storage._prefix(None)  # type: ignore

    assert "No valid value provided for key" in str(excinfo.value)


@pytest.mark.parametrize(
    "key,required",
    [
        (None, False),
        ("", False),
        ("valid_key", False),
        ("valid_key", True),
    ],
)
def test_validate_prefix_valid_cases(key, required):
    """Test _validate_prefix with valid inputs."""
    assert ABCStorage._validate_prefix(key, required=required) is True


@pytest.mark.parametrize(
    "key,required",
    [
        (None, True),
        ("", True),
    ],
)
def test_validate_prefix_invalid_required(key, required, caplog):
    """Test _validate_prefix raises KeyError when required=True and key is empty."""
    err = "non-empty namespace string must be provided"
    with pytest.raises(KeyError) as excinfo:
        ABCStorage._validate_prefix(key, required=required)

    assert err in str(excinfo.value)
    assert err in caplog.text


@pytest.mark.parametrize("invalid_key", [123, [], {}, object()])
def test_validate_prefix_invalid_type(invalid_key):
    """Test _validate_prefix raises KeyError for invalid types."""
    with pytest.raises(KeyError) as excinfo:
        ABCStorage._validate_prefix(invalid_key)  # type: ignore

    assert "non-empty namespace string must be provided" in str(excinfo.value)


def test_handle_storage_exception_logs_error(caplog):
    """Test _handle_storage_exception logs errors."""
    exception = ValueError("Test error")
    msg = "Custom error message"

    ABCStorage._handle_storage_exception(exception, msg=msg)

    assert msg in caplog.text


def test_handle_storage_exception_raises_when_specified():
    """Test _handle_storage_exception raises specified exception."""
    original_exception = ValueError("Original error")
    msg = "Custom error message"

    with pytest.raises(RuntimeError) as excinfo:
        ABCStorage._handle_storage_exception(original_exception, operation_exception_type=RuntimeError, msg=msg)

    assert msg in str(excinfo.value)


def test_with_raise_on_error_context_manager(abc_storage):
    """Test with_raise_on_error context manager."""
    assert abc_storage.raise_on_error is False

    with abc_storage.with_raise_on_error(True):
        assert abc_storage.raise_on_error is True

    # Should restore original value
    assert abc_storage.raise_on_error is False


def test_with_raise_on_error_nested(abc_storage):
    """Test nested with_raise_on_error context managers."""
    abc_storage.raise_on_error = False

    with abc_storage.with_raise_on_error(True):
        assert abc_storage.raise_on_error is True

        with abc_storage.with_raise_on_error(False):
            assert abc_storage.raise_on_error is False

        assert abc_storage.raise_on_error is True

    assert abc_storage.raise_on_error is False


def test_with_namespace_context_manager(abc_storage):
    """Test with_namespace context manager."""
    abc_storage.namespace = "ORIGINAL"

    with abc_storage.with_namespace("TEMPORARY"):
        assert abc_storage.namespace == "TEMPORARY"

    assert abc_storage.namespace == "ORIGINAL"


def test_with_namespace_nested(abc_storage):
    """Test nested with_namespace context managers."""
    abc_storage.namespace = "ORIGINAL"

    with abc_storage.with_namespace("FIRST"):
        assert abc_storage.namespace == "FIRST"

        with abc_storage.with_namespace("SECOND"):
            assert abc_storage.namespace == "SECOND"

        assert abc_storage.namespace == "FIRST"

    assert abc_storage.namespace == "ORIGINAL"


def test_structure_method(abc_storage):
    """Test structure method returns a string representation."""
    structure = abc_storage.structure()

    assert isinstance(structure, str)
    assert "ABCStorage" in structure
