from scholar_flux.utils.repr_utils import adjust_repr_padding, generate_repr, generate_repr_from_string
import pytest

class Dummy:
    """Class used to test and verify the representation of classes with repr utils"""
    def __init__(self):
        """Initializes the dummy class for testing"""
        self.attr1: int=1
        self.attr2: int=2
    """Test class for verifying the general structure used to create representations of classes and their attributes"""
    def __repr__(self) -> str:
        """Provides a basic representation of the dummy class (assuming the attributes are available)"""
        return "Dummy(\n    attr1=1,\n    attr2=2\n)"

class DummyNoPad:
    """Class used to test and verify the representation of classes with repr utils in the absence of padding"""
    def __init__(self):
        """Initializes the dummy class for testing"""
        self.attr1: int=1
        self.attr2: int=2

    def __repr__(self) -> str:
        """Simply returns the attributes of the class in the absence of spaces"""
        return "DummyNoPad(\nattr1=1,\nattr2=2\n)"


def test_single_line_representation_padding():
    """Verifies that simple primitive objects are not padded"""
    obj = 123
    obj_string = str(obj)
    obj_list = list(str(obj))

    assert adjust_repr_padding(obj) == generate_repr(obj) == "123"
    assert adjust_repr_padding(obj_string) == generate_repr(obj_string) == "123"
    assert adjust_repr_padding(obj_list) == generate_repr(obj_list) == "['1', '2', '3']"

def test_multi_line_representation_padding():
    """
    The basic `adjust_repr_padding` function, by default, only adjusts padding according to the length of the
    object name and where newline characters can be found
    """
    obj = Dummy()
    result = adjust_repr_padding(obj, pad_length=4)
    expected = "Dummy(\n        attr1=1,\n        attr2=2\n)"
    assert result == expected


def test_multi_line_representation_no_padding():
    """Verifies that the representation of non-padded classes, in the absence of separating spaces, will not change"""
    obj = DummyNoPad()
    result = adjust_repr_padding(obj, pad_length=2)
    # No leading spaces to adjust, should remain unchanged
    expected = "DummyNoPad(\nattr1=1,\nattr2=2\n)"
    assert result == expected

def test_different_pad_length():
    """Verifies that representation of variables with differing lengths successfully adds the required padding"""
    obj = Dummy()
    result = adjust_repr_padding(obj, pad_length=2)
    expected = "Dummy(\n      attr1=1,\n      attr2=2\n)"
    assert result == expected

@pytest.mark.parametrize("DummyClass", (Dummy, DummyNoPad))
def test_generated_representation(DummyClass):
    """Verifies that the default representation of the Dummy classes are generated based on its name and attributes"""
    dummy = DummyClass()
    
    # retrieves the name of the class
    class_name = dummy.__class__.__name__

    # representations operate by adding enough padding that each attribute is located  inline with the class parentheses
    spacing_length = len(class_name) + 1
    pad = spacing_length * " "

    dummy_repr = generate_repr(dummy)
    dummy_repr_from_string = generate_repr_from_string(class_name, dict(attr1=1,attr2=2))

    # verifies whether the spacing and methods used to create the padding is correct
    assert dummy_repr == dummy_repr_from_string == f"""{class_name}(attr1=1,\n{pad}attr2=2)"""

@pytest.mark.parametrize("DummyClass", (Dummy, DummyNoPad))
def test_single_line_generated_representation(DummyClass):
    """Verifies that the default flattened representation of the Dummy classes are represented on a single line"""
    dummy = DummyClass()

    # retrieves the name of the class
    class_name = dummy.__class__.__name__

    dummy_repr = generate_repr(dummy, flatten=True)
    dummy_repr_from_string = generate_repr_from_string(class_name, dict(attr1=1,attr2=2), flatten=True)

    # doesn't use padding, ignores the repr config and just prints class names, attributes and values
    assert dummy_repr == dummy_repr_from_string == f"""{class_name}(attr1=1, attr2=2)"""
