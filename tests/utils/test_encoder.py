from scholar_flux.utils.encoder import CacheDataEncoder, JsonDataEncoder
from collections import OrderedDict, UserDict, deque
from requests.utils import CaseInsensitiveDict
from scholar_flux.utils import RecursiveJsonProcessor
from typing import TypeVar
from base64 import b64encode
import pytest
import json

T = TypeVar("T")


@pytest.fixture
def turn_off_hash_prefix():
    """Hash prefix modification for future tests that validate without a prefix."""
    default_hash_prefix = CacheDataEncoder.DEFAULT_HASH_PREFIX
    CacheDataEncoder.DEFAULT_HASH_PREFIX = ""
    yield
    CacheDataEncoder.DEFAULT_HASH_PREFIX = default_hash_prefix


@pytest.fixture
def default_hash_prefix():
    return CacheDataEncoder.DEFAULT_HASH_PREFIX


def round_trip_data_encoder(data: T) -> T:
    """Helper function used to verify whether, after encoding, dumping, and recovering the initial data, The original
    result is returned.

    Args:
        data (T): A value encode and dump into a JSON string and reload and decode afterward

    Returns:
        T: The original type entered into the round_trip_data_encoder assuming the encoding and decoding is successful.
    """
    encoded = CacheDataEncoder.encode(data)
    json_string = json.dumps(encoded)
    from_json = json.loads(json_string)
    decoded = CacheDataEncoder.decode(from_json)
    return decoded


def round_trip_json_encoder(data: T) -> T:
    """Helper function used to serialize and deserialize data into the original input: This should produce the same
    result as the `round_trip_data_encoder` and is provided for testing purposes.

    Args:
        data (T): A value encode and dump into a JSON string and reload and decode afterward

    Returns:
        T: The original type entered into the round_trip_data_encoder assuming the encoding and decoding is successful.
    """
    serialized = JsonDataEncoder.serialize(data)
    deserialized = JsonDataEncoder.deserialize(serialized)
    return deserialized


@pytest.mark.parametrize(
    "data",
    (
        b"hello world",
        None,
        -1e20,
        0,
        0.0,
        1e50,
        True,
        False,
        "hello world",
        ["hello", "world"],
        {"hello": "world"},
        {"hello": b"world"},
        {"hello": [b"world", "!"]},
        {"a": b"bytes", "b": "string", "c": None, "d": [b"listbytes", "liststr", None]},
    ),
)
def test_encode_decode_roundtrip(data):
    """Verifies that the CacheDataEncoder, when encoding and decoding bytes results in the same value, even after being
    dumped into a JSON string and subsequently loaded.

    This test uses `pytest.mark.parametrize` in order to validate the
    different types of data that can be expected
    """
    result = round_trip_data_encoder(data)
    assert data == result == round_trip_json_encoder(data)


def test_tuple_roundtrip():
    """Verifies that tuples and sets can safely be encoded and decoded as needed when creating json dumpable data
    encoding.

    Note that, because types cannot be directly dumped via JSON, they
    must be coerced into lists instead.
    """

    # attempt to encode, dump and reload a tuple (coerced into a list)
    data = (b"bytes", "string", None)
    result = round_trip_data_encoder(data)
    # note that json dumps+loads results in lists becoming tuples
    assert data == tuple(result)


@pytest.mark.parametrize("DictType", (UserDict, CaseInsensitiveDict, OrderedDict))
def test_mapping_roundtrip(DictType, caplog):
    """Validates the use of the CacheDataEncoder when encoding dictionaries"."""
    dict_data = {"a": b"bytes", "b": "string"}
    data = DictType(dict_data)
    with caplog.at_level("WARNING"):
        encoded = CacheDataEncoder.encode(data)
        assert "Non-dictionary mutable mappings are coerced into dictionaries when encoded" in caplog.text
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == dict(data)


@pytest.mark.parametrize("SequenceType", (set, deque))
def test_sequence_roundtrip(SequenceType, caplog):
    """Validates the use of the CacheDataEncoder when encoding sequences"."""
    list_data = {"a": b"bytes", "b": "string"}
    data = SequenceType(list_data)
    with caplog.at_level("WARNING"):
        encoded = CacheDataEncoder.encode(data)
        assert "Non-list/tuple mutable sequences are coerced into lists when encoded" in caplog.text
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == list(data)


def test_base64():
    data = b"bytes string"
    encoded_data = b64encode(data)

    assert CacheDataEncoder.is_base64(encoded_data, hash_prefix="")
    assert not CacheDataEncoder.is_base64(data, hash_prefix="")
    with pytest.raises(ValueError) as excinfo:
        _ = CacheDataEncoder.is_base64(111)  # type: ignore
    assert "Argument must be string or bytes" in str(excinfo.value)

    assert not CacheDataEncoder.is_base64("")
    assert not CacheDataEncoder.is_base64(b"")

    assert not CacheDataEncoder.is_base64(b"")


def test_large_nested_structure():
    """Ensure encoder handles deeply nested structures."""
    data = {"level": 0}
    current: dict = data
    for i in range(100):  # 100 levels deep
        current["nested"] = {"level": i + 1, "data": b"bytes"}
        current = current["nested"]

    result = round_trip_data_encoder(data)
    assert data == result


def test_nonreadable_character_identification():
    """Tests the CacheDataEncoder.is_nonreadable class method to determine whether it correctly identifies non-readable
    characters.

    This test verifies that the classification of readable vs
    nonreadable characters also depends on `p` which is the proportion
    of non-readable byte characters, defined as unicode characters not
    between the range of (32 <= c <= 126)
    """
    nonreadable_character = b"\xc2\x80"
    assert not CacheDataEncoder.is_nonreadable(b"readable characters" + nonreadable_character, prop=0.1)
    assert CacheDataEncoder.is_nonreadable(nonreadable_character, prop=0.1)
    assert not CacheDataEncoder.is_nonreadable(b"   ", prop=1.0)


def test_json_roundtrip(mock_academic_json):
    """Simulates and tests the CacheDataEncoder/JsonDataEncoder against simulated JSON data to be encoded and decoded.

    The final result should be exactly equal to the initial result to
    ensure the robustness of encoding/decoding.
    """
    round_trip_result = round_trip_data_encoder(mock_academic_json)
    assert mock_academic_json == round_trip_result
    serialized = JsonDataEncoder.serialize(mock_academic_json)

    json_encoder_result = JsonDataEncoder.deserialize(serialized)
    assert mock_academic_json == json_encoder_result


def test_no_hash_prefix(default_hash_prefix, turn_off_hash_prefix, mock_academic_json):
    """Validates whether hash prefixes are successfully omitted when `DEFAULT_HASH_PREFIX` is turned off."""
    if not default_hash_prefix:
        pytest.skip(
            "A comparison of non hashed prefix behavior in the CacheDataEncoder must be performed only "
            "if DEFAULT_HASH_PREFIX is non missing"
        )

    encoded_json = CacheDataEncoder.encode(mock_academic_json)
    flattened_encoded_json = RecursiveJsonProcessor(encoded_json).process_and_flatten()
    assert flattened_encoded_json
    assert all(
        default_hash_prefix not in key and default_hash_prefix not in value
        for key, value in flattened_encoded_json.items()
        if key and value
    )


def test_no_hash_prefix_roundtrip(turn_off_hash_prefix, mock_academic_json):
    """Validates whether the CacheDataEncoder successfully encodes and decodes the json as is without modificaation when
    the CacheDataEncoder prefix is set to None."""
    assert not JsonDataEncoder.DEFAULT_HASH_PREFIX
    result = round_trip_json_encoder(mock_academic_json)
    assert mock_academic_json == result


def test_plos_page_roundtrip(turn_off_hash_prefix, plos_page_1_data, plos_page_2_data):
    """Verifies that without the use of a hash prefix, the round trip data encoder successfully encodes and decodes text
    to and from JSON serialized strings without data modification."""
    assert not JsonDataEncoder.DEFAULT_HASH_PREFIX
    result = round_trip_json_encoder(plos_page_1_data)
    assert plos_page_1_data == result

    result = round_trip_json_encoder(plos_page_2_data)
    assert plos_page_2_data == result


@pytest.mark.parametrize(
    ["transform", "value", "error_type"],
    (
        (
            CacheDataEncoder._encode_dict,
            ["a", "b", "c"],
            "Error encoding an element of type {current_type} into a recursively encoded dictionary",
        ),
        (
            CacheDataEncoder._decode_dict,
            ["a", "b", "c"],
            "Failed to decode an element of type {current_type} into a recursively decoded dictionary",
        ),
        (
            CacheDataEncoder._encode_list,
            11,
            "Error encoding an element of type {current_type} into a recursively encoded list",
        ),
        (
            CacheDataEncoder._decode_list,
            11,
            "Failed to decode an element of type {current_type} into a recursively decoded list",
        ),
        (
            CacheDataEncoder._encode_tuple,
            2,
            "Error encoding an element of type {current_type} into a recursively encoded tuple",
        ),
        (
            CacheDataEncoder._decode_tuple,
            3,
            "Failed to decode an element of type {current_type} into a recursively decoded tuple",
        ),
        (CacheDataEncoder._encode_bytes, 3, "Error encoding element of {current_type} into a base64 encoded string"),
    ),
)
def test_exception_handling(transform, value, error_type, caplog):
    """Tests a wide range of possible error scenarios where a value of a specific type cannot be encoded or decoded as
    intended.

    This test validates the error that is raised as well as the logged
    error message used to indicate the raised exception
    """
    with pytest.raises(ValueError) as excinfo:
        _ = transform(value)

    err = error_type.format(current_type=type(value))
    assert err in str(excinfo.value)
    assert err in caplog.text


def test_decode_string_exception(monkeypatch, caplog):
    """Helper method to validate the result returned by the CacheDataEncoder before and after accounting for possible
    errors.

    This function works by patching the `_is_nonreadable` helper
    function to raise a ValueError. As a result, possible scenarios are
    simulated where decoding bytes as string objects fails for whatever
    reason such as bad bytes and other TypeErrors/ValueErrors.
    """
    original_object = b"32"
    bytes_object = b64encode(original_object)
    value = CacheDataEncoder._decode_string(bytes_object)  # type: ignore
    assert original_object == value

    monkeypatch.setattr(
        CacheDataEncoder,
        "is_nonreadable",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Directly raised exception")),
    )

    value = CacheDataEncoder._decode_string(bytes_object)
    assert value == bytes_object
    assert f"Failed to decode a value of type {type(bytes_object)} as bytes" in caplog.text
    assert "Returning original input" in caplog.text
