"""Direct ABCProcessor tests to cover basic functionality before subclassed overrides.

This module verifies copy behavior and the override responsibilities of subclasses for No-Op methods and others that
should raise a `NotImplementedError` if not overridden.

Note: The following methods: `_validate_json_data()`, `_validate_inputs()`, and `structure()` are tested via processor
subclasses for completeness.

"""

import pytest
import copy
import threading
from scholar_flux.data.abc_processor import ABCDataProcessor


@pytest.fixture
def patch_abc_data_processor(monkeypatch):
    """Patches ABCDataProcessor to allow direct instantiation for testing base class methods."""
    monkeypatch.setattr(ABCDataProcessor, "__abstractmethods__", set())


@pytest.fixture()
def abc_data_processor(patch_abc_data_processor) -> ABCDataProcessor:
    """Creates a basic ABCDataProcessor bypassing the abstract method checks."""
    return ABCDataProcessor()  # type: ignore


def test_abc_data_processor_initialization(patch_abc_data_processor):
    """Test basic initialization of the ABCDataProcessor subclass."""
    assert ABCDataProcessor()  # type: ignore


def test_not_implemented_functionality(abc_data_processor):
    """Verifies that functionality to be subclassed raises a NotImplementedError if not subclassed."""
    NOT_IMPLEMENTED = (
        abc_data_processor.load_data,
        abc_data_processor.process_page,
        abc_data_processor.__call__,
    )
    for processor_method in NOT_IMPLEMENTED:
        with pytest.raises(NotImplementedError):
            processor_method()


def test_noop_functionality(abc_data_processor):
    """Verifies No-Op methods at the level of the ABCDataProcessor.

    Each method should return None.

    """
    NO_OP_FUNCTIONALITY = (
        abc_data_processor.define_record_keys,
        abc_data_processor.ignore_record_keys,
        abc_data_processor.define_record_path,
        abc_data_processor.record_filter,
        abc_data_processor.discover_keys,
        abc_data_processor.process_key,
        abc_data_processor.process_text,
        abc_data_processor.process_record,
    )
    for processor_method in NO_OP_FUNCTIONALITY:
        assert processor_method() is None


def test_copy_does_not_raise(patch_abc_data_processor):
    """Test that `copy` does not encounter an unexpected error when called."""
    abc_data_processor = ABCDataProcessor()  # type: ignore
    abc_data_processor.data = ["random entry"]  # type: ignore
    abc_data_processor._lock = threading.Lock()  # type: ignore
    abc_data_processor_copy = copy.copy(abc_data_processor)
    LOCK_TYPE = type(threading.Lock())
    assert abc_data_processor_copy.data == abc_data_processor.data  # type: ignore
    assert isinstance(abc_data_processor._lock, LOCK_TYPE)  # type: ignore
    assert isinstance(abc_data_processor_copy._lock, LOCK_TYPE)  # type: ignore
    assert abc_data_processor._lock is not abc_data_processor_copy._lock  # type: ignore


def test_deepcopy_does_not_raise(patch_abc_data_processor):
    """Test that `deepcopy` does not encounter an unexpected error when called."""
    abc_data_processor = ABCDataProcessor()  # type: ignore
    abc_data_processor.data = ["random entry"]  # type: ignore
    abc_data_processor._lock = threading.Lock()  # type: ignore
    abc_data_processor_copy = copy.deepcopy(abc_data_processor)
    LOCK_TYPE = type(threading.Lock())
    assert abc_data_processor_copy.data == abc_data_processor.data  # type: ignore
    assert isinstance(abc_data_processor._lock, LOCK_TYPE)  # type: ignore
    assert isinstance(abc_data_processor_copy._lock, LOCK_TYPE)  # type: ignore
    assert abc_data_processor._lock is not abc_data_processor_copy._lock  # type: ignore
