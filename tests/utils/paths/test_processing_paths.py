from scholar_flux.utils.paths import ProcessingPath
from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    InvalidPathDelimiterError,
    InvalidComponentTypeError,
)
import pytest


def test_initialization():
    """Validates the initialization of ProcessingPaths with a variety of components/component_types"""
    basic_path = ProcessingPath(components=["1", "2", "3"], component_types=["odd", "even", "odd"])
    assert isinstance(basic_path, ProcessingPath)

    assert ProcessingPath().depth == 0
    assert ProcessingPath(("",)).depth == 0
    assert (
        ProcessingPath(
            [
                "",
            ]
        ).depth
        == 0
    )
    assert ProcessingPath("").depth == 0
    assert ProcessingPath(None).depth == 0  # type: ignore

    basic_path = ProcessingPath(components=["1", "2", "3"], component_types=None)
    assert basic_path

    basic_path_int = ProcessingPath(components=[1, 2, 3], component_types=["odd", "even", "odd"])
    assert basic_path == basic_path_int  # discouraged to use integers but allowed

    basic_path = ProcessingPath(components=["1", "2", "3"], component_types=[] * 3)
    assert basic_path

def test_invalid_path_initialization():
    """Validates the exception raising of paths when invalid combinations of inputs are entered"""
    basic_path = ProcessingPath(components=["1", "2", "3"], component_types=[] * 3, delimiter=None)

    with pytest.raises(InvalidProcessingPathError):
        # Shouldn't be able to infer a path for a list, we just initialize a path regularly: ProcessingPath(...)
        _ = ProcessingPath.to_processing_path(basic_path.to_list(), infer_delimiter=True)

    assert basic_path.delimiter == ProcessingPath.DEFAULT_DELIMITER

    assert basic_path == ProcessingPath.to_processing_path(basic_path)
    assert basic_path == ProcessingPath.to_processing_path(basic_path.to_list())
    assert basic_path == tuple(basic_path.to_list())

    assert basic_path == ProcessingPath.to_processing_path(basic_path.delimiter.join(basic_path.components))

    with pytest.raises(InvalidComponentTypeError):
        basic_path = ProcessingPath(components=["1", "2", "3"], component_types=["odd", "even"])

    with pytest.raises(InvalidProcessingPathError):
        basic_path = ProcessingPath(components=["No", "", "Yes"], component_types=["false", "0", "even"])

    with pytest.raises(InvalidPathDelimiterError):
        basic_path = ProcessingPath(components=["No", "Yes"], component_types=["false", "even"], delimiter="^")


def test_components():
    """Verifies the basic functioning of processing paths including components, component types, and key membership"""
    basic_path = ProcessingPath(components=["1", "2", "3"], component_types=["odd", "even", "odd"])
    assert isinstance(basic_path, ProcessingPath)

    assert basic_path.depth == 3
    assert basic_path.components[0] == "1"
    assert basic_path.components[1] == "2"
    assert basic_path.components[2] == "3"

    assert basic_path.component_types is not None

    assert basic_path.component_types[0] == "odd"

    assert basic_path.component_types[1] == "even"

    assert basic_path.component_types[2] == "odd"

    assert ("2", "3") in basic_path
    assert ["1", "2"] in basic_path
    assert ["1", "3"] not in basic_path


def test_equality():
    path_one = ProcessingPath(components=["1", "2", "30"])
    path_two = ProcessingPath(components=["1", "2", "9"])

    assert path_one > path_two
    assert path_one >= path_two

    assert path_two <= path_one
    assert path_two < path_one

    assert path_one == path_one
    assert not path_one != path_one  # noqa: SIM202 (Ensure __ne__ works as intended)


def test_indices():
    original_keys = ("key1", "1", "key2", "2", "key3")
    replaced_keys = ("key1", "i", "key2", "i", "key3")
    path_one = ProcessingPath(components=original_keys)
    assert original_keys in path_one

    assert replaced_keys in path_one.replace_indices()


def test_update_delimiter():
    path_one = ProcessingPath(components=["1", "2", "30"])
    path_two = path_one.update_delimiter("%")
    assert path_two.delimiter == "%"
    assert path_two.delimiter != path_one


def test_update_values():
    path_one = ProcessingPath(components=["1", "2", "30"])
    path_two = path_one.update_delimiter("%")
    assert path_two.delimiter == "%"
    assert path_two.delimiter != path_one


@pytest.mark.parametrize("delimiter", ["<>", "//", "/", ">", "<", "\\", "%", "."])
def test_delimiters(delimiter):
    components = ["1", "2", "3"]
    basic_path = ProcessingPath(components)
    component_str = delimiter.join(components)

    inferred_delim_path = ProcessingPath.with_inferred_delimiter(component_str)
    assert basic_path in inferred_delim_path
    assert delimiter == inferred_delim_path.delimiter


def test_root():
    root_path = ProcessingPath([""])
    basic_path = ProcessingPath(["1", "2", "3"])

    assert root_path.depth == 0
    assert root_path.components == ("",)
    assert root_path.is_root is True
    assert not root_path

    assert root_path.is_ancestor_of(basic_path)
    assert basic_path.has_ancestor(root_path)


def test_getitem():
    basic_path = ProcessingPath(["0", "1", "2", "3", "4", "5", "6"])

    assert basic_path.components[0:2] == basic_path[0:2].components
    assert basic_path.components[-2:] == basic_path[-2:].components


def test_replace_path():
    final_path = ProcessingPath(["3", "4", "5", "6", "3", "4", "5", "6"])
    initial_path = ProcessingPath(["0", "1", "2", "3", "4", "5", "6"])

    old = initial_path[:3]
    new = initial_path[3:]

    assert initial_path.replace_path(old, new).components == final_path.components

    with pytest.raises(InvalidProcessingPathError):
        # replace replaces only string, replace_path is more preferable in this case
        initial_path.replace(initial_path[:3], initial_path[3:])  # type:ignore

    assert initial_path.replace(initial_path[-1].to_string(), "i") == initial_path[:-1] / "i"

    with pytest.raises(InvalidProcessingPathError):
        # implausable substitution
        _ = initial_path.replace(6, "i")  # type:ignore


def test_hash():
    path_one = ProcessingPath(["1", "2"], delimiter=".")
    path_two = ProcessingPath(["2", "3"], delimiter="/")
    path_three = ProcessingPath(["3", "4"], delimiter="%")

    path_dict = {path_one: 1, path_two: 2, path_three: 3}

    assert path_one.to_string() in path_dict
    assert path_two.to_string() in path_dict
    assert path_three.to_string() in path_dict

    assert path_one in path_dict
    assert path_two in path_dict
    assert path_three in path_dict

    assert path_one[:1] not in path_dict
    assert ProcessingPath([""]) not in path_dict
    assert path_one / path_two not in path_dict


def test_ancestors():
    path_one = ProcessingPath(["1", "2", "0"], component_types=["one", "two", "zero"])

    ancestors = path_one.get_ancestors()
    assert path_one[:-1] in ancestors
    assert path_one[:-2] in ancestors

    path_root = ProcessingPath("")

    assert path_root.get_ancestors() == []


def test_remove():
    path_one = ProcessingPath(["1", "2", "0"], component_types=["one", "two", "zero"])
    path_two = path_one.remove(["0"])
    assert len(path_one) == 3
    assert path_two.depth == 2
    assert ("1", "2") in path_two
    assert path_two.is_ancestor_of(path_one)

    assert path_two.component_types and "zero" not in path_two.component_types


def test_remove_by_type():
    path_one = ProcessingPath(["1", "2", "0"], component_types=["one", "two", "zero"])
    path_two = path_one.remove_by_type(["zero"])
    assert len(path_one) == 3
    assert path_two.depth == 2
    assert ("1", "2") in path_two
    assert path_two.is_ancestor_of(path_one)
    assert path_two.is_ancestor_of(path_one.to_string())
    assert path_one.has_ancestor(path_two.to_string())

    assert path_two.component_types and "zero" not in path_two.component_types


def test_info_content():
    path_one = ProcessingPath(["1", "2", "NA", "3", "NA", "5"])
    path_not_null = path_one.remove(["NA"])
    assert path_one.info_content(["NA"]) == 4 == path_not_null.depth


def test_append():
    final_path = ProcessingPath(["1", "2", "3", "4", "5"])
    path = ProcessingPath(["1"])
    assert path == final_path[:1]
    path = path.append("2").append("3").append("4").append("5")
    assert path == final_path

    with pytest.raises(InvalidProcessingPathError):
        path = path.append(6)  # type:ignore

    with pytest.raises(InvalidProcessingPathError):
        path = path.append("")

    path_two = ProcessingPath(["1", "2", "3"], ["one", "two", "three"])
    path_two = path_two.append("4", "four")
    assert path_two.components == ("1", "2", "3", "4")
    assert path_two.component_types == ("one", "two", "three", "four")


def test_pipe():
    final_path = ProcessingPath(["0", "1", "2", "3", "4", "5", "6"])
    path_one = ProcessingPath(["0", "1", "2"])
    path_two = ProcessingPath(["3", "4", "5", "6"])

    assert (path_one / path_two) == final_path
    assert (path_two / path_one).sorted() == final_path

    assert (ProcessingPath() / ProcessingPath()).depth == 0
    assert (ProcessingPath() / "").depth == 0
    assert (ProcessingPath() / "" / ProcessingPath()).depth == 0


def test_keep_descendants():
    initial_paths = [
        ProcessingPath("a<>b", delimiter="<>"),
        ProcessingPath("b<>b", delimiter="<>"),
        ProcessingPath("c<>b", delimiter="<>"),
        ProcessingPath("a", delimiter="<>"),
        ProcessingPath("b", delimiter="<>"),
        ProcessingPath("d", delimiter="<>"),
        ProcessingPath("e", delimiter="<>"),
        ProcessingPath("c<>b<>f<>g", delimiter="<>"),
    ]

    descendants = ProcessingPath.keep_descendants(initial_paths)

    assert len(descendants) == 5
    assert len([d for d in descendants if d.depth == 1]) == 2
    assert len([d for d in descendants if d.depth != 1]) == 3
    paths = (
        ProcessingPath(("a", "b"), delimiter="<>"),
        ProcessingPath(("b", "b"), delimiter="<>"),
        ProcessingPath(("c", "b", "f", "g"), delimiter="<>"),
        ProcessingPath(("d",), delimiter="<>"),
        ProcessingPath(("e",), delimiter="<>"),
    )

    assert all(path in descendants for path in paths)
