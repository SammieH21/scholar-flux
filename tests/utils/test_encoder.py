from scholar_flux.utils.encoder import CacheDataEncoder, JsonDataEncoder
from collections import OrderedDict, UserDict, deque
from requests.utils import CaseInsensitiveDict
from typing import TypeVar
from base64 import b64encode
import pytest
import json

T = TypeVar("T")


def round_trip_data_encoder(data: T) -> T:
    """
    Helper function used to verify whether, after encoding, dumping, and recovering the initial data,
    The original result is returned.

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
    """
    Helper function used to serialize and deserialize data into the original input:
        This should produce the same result as the `round_trip_data_encoder` and is provided for testing purposes.

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
    """
    Verifies that the CacheDataEncoder, when encoding and decoding bytes results in the same value, even
    after being dumped into a JSON string and subsequently loaded.

    This test uses `pytest.mark.parametrize` in order to validate the different types of data that can
    be expected
    """
    result = round_trip_data_encoder(data)
    assert data == result == round_trip_json_encoder(data)


def test_tuple_roundtrip():
    """
    Verifies that tuples and sets can safely be encoded and decoded as needed when creating json dumpable data encoding.
    Note that, because types cannot be directly dumped via JSON, they must be coerced into lists instead.
    """

    # attempt to encode, dump and reload a tuple (coerced into a list)
    data = (b"bytes", "string", None)
    result = round_trip_data_encoder(data)
    # note that json dumps+loads results in lists becoming tuples
    assert data == tuple(result)


@pytest.mark.parametrize("DictType", (UserDict, CaseInsensitiveDict, OrderedDict))
def test_mapping_roundtrip(DictType, caplog):
    """
    Validates the use of the CacheDataEncoder when encoding dictionaries"
    """
    dict_data = {"a": b"bytes", "b": "string"}
    data = DictType(dict_data)
    with caplog.at_level("WARNING"):
        encoded = CacheDataEncoder.encode(data)
        assert "Non-dictionary mutable mappings are coerced into dictionaries when encoded" in caplog.text
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == dict(data)


@pytest.mark.parametrize("SequenceType", (set, deque))
def test_sequence_roundtrip(SequenceType, caplog):
    """
    Validates the use of the CacheDataEncoder when encoding sequences"
    """
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


def test_nonreadable_character_identification():
    """
    Verifies that the classification of readable vs nonreadable characters also depends on `p` which is the proportion
    of non-readable byte characters, defined as unicode characters not between the range of (32 <= c <= 126)
    """
    nonreadable_character = b"\xc2\x80"
    assert not CacheDataEncoder.is_nonreadable(b"readable characters" + nonreadable_character, p=0.1)
    assert CacheDataEncoder.is_nonreadable(nonreadable_character, p=0.1)
    assert not CacheDataEncoder.is_nonreadable(b"   ", p=1)


def test_json_roundtrip(mock_academic_json):
    """
    Simulates and tests the CacheDataEncoder/JsonDataEncoder against simulated JSON data to be encoded and decoded.

    The final result should be exactly equal to the initial result to ensure the robustness of encoding/decoding.
    """
    round_trip_result = round_trip_data_encoder(mock_academic_json)
    assert mock_academic_json == round_trip_result
    serialized = JsonDataEncoder.serialize(mock_academic_json)

    json_encoder_result = JsonDataEncoder.deserialize(serialized)
    assert mock_academic_json == json_encoder_result


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
    """
    Tests a wide range of possible error scenarios where a value of a specific type cannot be encoded or decoded as intended.

    This test validates the error that is raised as well as the logged error message used to indicate the raised exception
    """
    with pytest.raises(ValueError) as excinfo:
        _ = transform(value)

    err = error_type.format(current_type=type(value))
    assert err in str(excinfo.value)
    assert err in caplog.text


def test_decode_string_exception(monkeypatch, caplog):
    """
    Helper method to validate the result returned by the CacheDataEncoder before and after accounting for possible errors.

    This function works by patching the `_is_nonreadable` helper function to raise a ValueError.
    As a result, possible scenarios are simulated where decoding bytes as string objects fails for whatever reason such as
    bad bytes and other TypeErrors/ValueErrors.
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
