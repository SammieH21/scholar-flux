import pytest
from copy import deepcopy
from scholar_flux.exceptions import InvalidPathNodeError
from scholar_flux.utils.paths import (
    ProcessingPath,
    PathNode,
)


def test_node_deep_copy():
    """Testing the deep copying method for the PathNode"""
    test_value = [1, 2, 3]
    node = PathNode.to_path_node(path="a.b.c", value=test_value)
    new_node = deepcopy(node)

    node.value.append(4)
    assert node.value != new_node.value


def test_pathnode_creation_and_properties():
    """Validates the initialization of a new path node and determines whether properties are accessible"""
    path_components = ["0", "data", "0", "title"]
    node_value = "Correction: Mitochondrial flux impacts tumor cell survival under hypoxic conditions"
    path = ProcessingPath(path_components)
    node = PathNode(path, node_value)
    assert node.path == path
    assert node.value.startswith("Correction")
    assert node.path_keys == ProcessingPath(["data", "title"])
    assert node.path_group.components[-1] == "i" or node.path_group.components[-1] == "title"
    assert node.record_index == 0

    node2 = PathNode.to_path_node(path_components, node_value)
    assert node == node2 and node.value == node.value

    path_node1 = PathNode.to_path_node(1, value=1)  # type: ignore
    path_node2 = PathNode.to_path_node("1", value=1)

    assert path_node1 == path_node2


def test_invalid_node_creation():
    """Verifies that attempting to create nodes with invalid values raises an error as intended"""
    with pytest.raises(InvalidPathNodeError):
        _ = PathNode(None, value=1)  # type:ignore

    with pytest.raises(InvalidPathNodeError):
        _ = PathNode([1, 2, 3], value=1)  # type:ignore

    with pytest.raises(InvalidPathNodeError):
        _ = PathNode.to_path_node(None, value=1)  # type:ignore


def test_pathnode_update_and_equality():
    """Verifies that updates to path nodes wll create new nodes entirely without the modification of the previous"""
    path = ProcessingPath(["0", "data", "0", "title"])
    node = PathNode(path, "A")
    copied_node = node.copy()
    updated = node.update(value="B")
    assert updated.value == "B"
    assert updated.path == node.path
    assert node != updated
    assert node == copied_node
    assert hash(node) == hash(node.path)
