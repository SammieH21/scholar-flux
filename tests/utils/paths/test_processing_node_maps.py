from typing import MutableMapping
import pytest
from scholar_flux.utils import PathNode, PathNodeMap, ProcessingPath


@pytest.fixture
def default_mapping():
    """Fixture used to verify the functionality used in a basic path node map"""
    x1 = PathNode.to_path_node("a.b.c.1", 1)
    x2 = PathNode.to_path_node("a.b.c.2", 2)
    x3 = PathNode.to_path_node("a.b.c.3", 3)
    x4 = PathNode.to_path_node("a.b.c.4", 4)
    default_mapping = PathNodeMap(x1, x2, x3, x4)
    return default_mapping


def test_map_initialization():
    """
    Verifies different methods used to initialize a new PathNodeMap and determine whether each
    results in identical node maps
    """
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
    """Validates whether nodes can be identified as being present within a mapping by path and node"""
    (x1, _, _, x4) = default_mapping.nodes
    assert "a" not in default_mapping
    assert None not in default_mapping
    assert x1.path in default_mapping
    assert str(x1.path) in default_mapping
    assert x1 in default_mapping

    last_node = default_mapping.nodes[-1]
    assert last_node == x4

    assert last_node in default_mapping
    assert last_node.path in default_mapping
    assert last_node.path[:-1] / "non-existent value" not in default_mapping


def test_retrieve(default_mapping):
    """Verifies that the retrieval of nodes can occur via the use of both ProcessingPaths and path strings"""
    (x1, _, _, x4) = default_mapping.nodes

    assert default_mapping.retrieve(x1.path) == x1
    assert default_mapping.retrieve(str(x1.path)) == x1
    assert default_mapping.retrieve(x4.path) == x4

    assert default_mapping.get(None) is None
    assert default_mapping.retrieve(None) is None


def test_pathnodemap_add_get_remove():
    """Verifies that the removal of nodes operates as intended to both add and remove paths inplace"""
    path = ProcessingPath(["0", "data", "0", "title"])
    node = PathNode(path, "A")
    m = PathNodeMap()
    m.add(node)
    assert m.get(path) == node
    assert path in m
    m.remove(path)
    assert m.get(path) is None


def test_pathnodemap_filter_and_cache():
    """Verifies whether filtering node maps will returns the intended result independent of the use of caching"""
    m = PathNodeMap(cache=True)
    nodes = [PathNode(ProcessingPath(["0", "data", str(i), "title"]), f"title_{i}") for i in range(3)]
    for node in nodes:
        m.add(node)
    filtered = m.filter(ProcessingPath(["0", "data"]), min_depth=3)
    assert all(n.path in filtered for n in nodes)
    # Enable cache and test cache_filter
    m.cache = True
    filtered_cache = m.filter(ProcessingPath(["0", "data"]), from_cache=True)
    assert filtered_cache == filtered
