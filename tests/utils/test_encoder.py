from scholar_flux.utils.encoder import CacheDataEncoder
from collections import OrderedDict, deque


def test_bytes_roundtrip():
    data = b"hello world"
    encoded = CacheDataEncoder.encode(data)
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == data


def test_string_roundtrip():
    data = "hello world"
    encoded = CacheDataEncoder.encode(data)
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == data


def test_none_roundtrip():
    data = None
    encoded = CacheDataEncoder.encode(data)
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded is None


def test_dict_mixed_types():
    data = {"a": b"bytes", "b": "string", "c": None, "d": [b"listbytes", "liststr", None]}
    encoded = CacheDataEncoder.encode(data)
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == data


def test_tuple_mixed_types():
    data = (b"bytes", "string", None)
    encoded = CacheDataEncoder.encode(data)
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == data


def test_ordereddict_warning(caplog):
    data = OrderedDict([("a", b"bytes"), ("b", "string")])
    with caplog.at_level("WARNING"):
        encoded = CacheDataEncoder.encode(data)
        assert "coerced into dictionaries" in caplog.text
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == dict(data)


def test_deque_warning(caplog):
    data = deque([b"bytes", "string"])
    with caplog.at_level("WARNING"):
        encoded = CacheDataEncoder.encode(data)
        assert "coerced into lists" in caplog.text
    decoded = CacheDataEncoder.decode(encoded)
    assert decoded == list(data)
