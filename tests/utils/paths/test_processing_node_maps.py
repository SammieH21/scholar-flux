import pytest
from typing import MutableMapping
from scholar_flux.utils import (
    ProcessingPath,
    PathNode,
    PathNodeMap,
)


def test_map_initialization():
    x1 = PathNode(ProcessingPath('a.b.c.1'), 1)
    x2 = PathNode(ProcessingPath('a.b.c.2'), 2)
    x3 = PathNode(ProcessingPath('a.b.c.3'), 3)
    x4 = PathNode(ProcessingPath('a.b.c.4'), 4)

    node_tuple = (x1, x2, x3, x4)
    node_map = PathNodeMap(node_tuple)
    assert len(node_map) == 4
    assert isinstance(node_map, MutableMapping)
    assert isinstance(node_map, PathNodeMap)

    node_list = [x.copy() for x in node_tuple]

    node_map = PathNodeMap(*(x1, x2, x3, x4))
