from typing import MutableMapping
import pytest
from scholar_flux.utils import (
    # ProcessingPath,
    PathNode,
    PathNodeMap,
)

@pytest.fixture
def default_mapping():
    x1 = PathNode.to_path_node("a.b.c.1", 1)
    x2 = PathNode.to_path_node("a.b.c.2", 2)
    x3 = PathNode.to_path_node("a.b.c.3", 3)
    x4 = PathNode.to_path_node("a.b.c.4", 4)
    default_mapping = PathNodeMap(x1, x2, x3, x4)
    return default_mapping

def test_map_initialization():
    x1 = PathNode.to_path_node("a.b.c.1", 1)
    x2 = PathNode.to_path_node("a.b.c.2", 2)
    x3 = PathNode.to_path_node("a.b.c.3", 3)
    x4 = PathNode.to_path_node("a.b.c.4", 4)

    node_tuple = (x1, x2, x3, x4)
    node_map = PathNodeMap(node_tuple)  # type: ignore
    assert len(node_map) == 4
    assert isinstance(node_map, MutableMapping)
    assert isinstance(node_map, PathNodeMap)

    node_list = [x.copy() for x in node_tuple]
    node_map2 = PathNodeMap(node_list)

    node_map3 = PathNodeMap(*(x1.copy(), x2.copy(), x3.copy(), x4.copy()))
    assert node_map == node_map2 == node_map3

def test_contains(default_mapping):


    (x1, _, _, x4) = default_mapping.nodes
    assert 'a' not in default_mapping
    assert None not in default_mapping
    assert x1.path in default_mapping
    assert str(x1.path) in default_mapping
    assert x1 in default_mapping

    last_node = default_mapping.nodes[-1]
    assert last_node == x4

    assert last_node in default_mapping
    assert last_node.path in default_mapping
    assert last_node.path[:-1] / 'non-existent value' not in default_mapping


def test_retrieve(default_mapping):
    (x1, _, _, x4) = default_mapping.nodes

    assert default_mapping.retrieve(x1.path) == x1
    assert default_mapping.retrieve(str(x1.path)) == x1
    assert default_mapping.retrieve(x4.path) == x4

    assert default_mapping.get(None) is None
    assert default_mapping.retrieve(None) is None
