import pytest
from scholar_flux.utils.repr_utils import adjust_repr_padding


class Dummy:
    def __repr__(self):
        return "Dummy(\n    attr1=1,\n    attr2=2\n)"

def test_single_line_representation():
    obj = 123
    assert adjust_repr_padding(obj) == "123"

def test_multi_line_representation_padding():
    obj = Dummy()
    result = adjust_repr_padding(obj, pad_length=4)
    expected = "Dummy(\n        attr1=1,\n        attr2=2\n)"
    assert result == expected

def test_multi_line_representation_no_padding():
    class NoPad:
        def __repr__(self):
            return "NoPad(\nattr1=1,\nattr2=2\n)"
    obj = NoPad()
    result = adjust_repr_padding(obj, pad_length=2)
    # No leading spaces to adjust, should remain unchanged
    expected = "NoPad(\nattr1=1,\nattr2=2\n)"
    assert result == expected

def test_different_pad_length():
    obj = Dummy()
    result = adjust_repr_padding(obj, pad_length=2)
    expected = "Dummy(\n      attr1=1,\n      attr2=2\n)"
    assert result == expected
