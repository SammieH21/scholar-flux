from __future__ import annotations

from scholar_flux.exceptions.path_exceptions import (
    InvalidPathNodeError,
    InvalidProcessingPathError,
    PathRecordMapError,
    PathNodeMapError,
    PathChainMapError,
    InvalidPathNodeError
)
import pytest


from scholar_flux.utils.paths import (ProcessingPath,
                                      PathNode,
                                      PathNodeMap,
                                      PathRecordMap,
                                      PathChainMap
                                     )

@pytest.fixture
def all_path_nodes():

    all_path_nodes = []
    for i in range(10):
        idx = i
        path_nodes = [PathNode.to_path_node(f'{i}.a.{x}', i) for x in ('a', 'b', 'c', 'd')]

        path_records = PathRecordMap(*path_nodes, record_index = idx)
        all_path_nodes.append(path_records)
    return all_path_nodes

@pytest.fixture
def default_mapping(all_path_nodes):
    default_mapping = PathChainMap(*all_path_nodes)
    return default_mapping

def test_blank_initialization():
   mapping = PathChainMap()
   mapping_two = PathChainMap({})
   assert mapping == mapping_two

def test_initialization(all_path_nodes):
   mapping = PathChainMap()
   assert len(mapping) == 0

   for record_map in all_path_nodes:
       mapping[record_map.record_index] = record_map

   assert len(mapping) == 10
   assert len(mapping.nodes) == 40

   mapping_two = PathChainMap(*all_path_nodes)
   assert mapping == mapping_two


   mapping_three = PathChainMap()
   mapping_three.update(*all_path_nodes)

   assert mapping_three == mapping

   mapping_four = PathChainMap()
   nodes = [node for node_map in all_path_nodes for node in node_map.values()]
   assert len(set(node.path for node in nodes)) == 40
   mapping_four.update(*(node for node_map in all_path_nodes for node in node_map.values()))

   assert len(mapping_four) == 10
   assert all(isinstance(path, PathRecordMap) for path in mapping_four.data.values())
   assert len(mapping_four.nodes) == 40

   mapping_five = PathChainMap()
   for node in nodes:
       mapping_five.add(node)
   assert mapping_five == mapping

def test_inferred_record_index():
    a1 = PathNode.to_path_node(f"1.a", value = 1)
    a2 = PathNode.to_path_node(f"1.b", value = 2)
    a3 = PathNode.to_path_node(f"1.c", value = 3)

    record_map = PathRecordMap(a1,a2,a3)

    assert record_map.record_index == 1

    record_dict = {str(a.path): a for a in (a1, a2, a3)}
    mapping = PathNodeMap()
    mapping.format_mapping(record_dict)
    record_map_two = PathRecordMap(**record_dict)

    assert record_map_two.record_index == 1
    assert record_map_two == record_map

    with pytest.raises(PathRecordMapError) as excinfo:
        _ = PathRecordMap()
    assert "A numeric record index is missing and could not be inferred from the input nodes" in str(excinfo.value)

    with pytest.raises(InvalidPathNodeError) as excinfo:
        _ = PathRecordMap(' ')
    assert f"The current object is not a PathNode: expected 'PathNode', received {type(' ')}" in str(excinfo.value)

def test_formatting(all_path_nodes):
    positional_params = (node for record in all_path_nodes[5:] for node in record.values())
    keyword_params = {str(path): node
                      for record in all_path_nodes[:5] for path, node in record.items()}

    assert positional_params
    assert keyword_params
    mapping = PathChainMap()
    
    formatted_mappings = PathNodeMap._format_nodes_as_dict(*positional_params, **keyword_params)
    assert len(formatted_mappings) == 40

    mapping.update(*all_path_nodes)
    assert mapping.nodes == list(formatted_mappings.values())
    assert mapping.paths == list(formatted_mappings.keys())

def test_invalid_formatting():
    new_path_node = PathRecordMap(record_index = 1)
    invalid_path_node = {'a':' '}
    with pytest.raises (PathNodeMapError) as excinfo:
        _ = new_path_node._format_nodes_as_dict(invalid_path_node)
    assert ("Could not format the input as a dictionary of nodes: Expected the input to be a "
            f"PathNode or sequence/mapping containing PathNodes. Instead received {type(invalid_path_node)}") in str(excinfo.value)


def test_record_map_creation():
    a1 = PathNode.to_path_node(f"1.a", value = 1)
    a2 = PathNode.to_path_node(f"1.b", value = 2)
    a3 = PathNode.to_path_node(f"1.c", value = 3)
    seq = [a1, a2, a3]
    mapping = {a1.path: a1, a2.path: a2, a3.path: a3}
    record_map = PathRecordMap.from_mapping(seq)
    record_map_two = PathRecordMap.from_mapping(mapping)
    assert len(record_map) ==3
    assert record_map == record_map_two
    record_map_three = PathRecordMap.from_mapping(record_map_two)
    assert record_map_three == record_map_two

    record_map_single = PathRecordMap({a1.path: a1})
    assert len(record_map_single) == 1

    assert record_map_single == PathRecordMap(a1)

    record_map_single_two = PathRecordMap(a1)
    assert record_map_single == record_map_single_two
    record_map_single_three = PathRecordMap([a1])
    assert record_map_single_three == record_map_single

    record_map_single_four = PathRecordMap({a1})
    assert record_map_single_four == record_map_single

def test_chain_input_preparation():
    a1 = PathNode.to_path_node(f"2.a", value = 1)
    a2 = PathNode.to_path_node(f"2.b", value = 2)
    a3 = PathNode.to_path_node(f"2.c", value = 3)

    prepped_inputs = PathRecordMap._prepare_inputs([a1, a2, a3])
    assert prepped_inputs == (2, [a1, a2, a3])

    prepped_inputs_two = PathRecordMap._prepare_inputs([a1])
    assert prepped_inputs_two == (2, [a1])

    prepped_inputs_three = PathRecordMap._prepare_inputs(a1)
    assert prepped_inputs_two == prepped_inputs_three

    bad_node = "not a node"

    with pytest.raises(PathRecordMapError) as excinfo:
        _ = PathRecordMap._prepare_inputs(bad_node)
    assert ("Encountered an error on the preparation of inputs for a PathRecordMap: "
            "The current object is not a PathNode") in str(excinfo.value)

    another_bad_node = 1100

    with pytest.raises(PathRecordMapError) as excinfo:
        _ = PathRecordMap._prepare_inputs(another_bad_node)
    assert ("Expected a sequence of nodes, but at least one value is of a different type") in str(excinfo.value)

def test_invalid_record_indices():
    a1 = PathNode.to_path_node(f"1.a", value = 1)
    b1 = PathNode.to_path_node(f"2.g", value = 3)

    with pytest.raises(PathRecordMapError) as excinfo:
        _ = PathRecordMap._prepare_inputs([a1, b1])
    assert ("Expected a mapping or sequence with exactly 1 record_index, "
            f"Received: [1, 2]") in str(excinfo.value)


def test_record_map_resolution(all_path_nodes):
    record_map_one = PathChainMap._resolve_record_maps(*all_path_nodes)
    record_map_two = PathChainMap._resolve_record_maps(
        *(node for node_map in all_path_nodes for node in node_map.values())
    )

    record_map_three = PathChainMap._resolve_record_maps(
        *(PathNodeMap(node_map) for node_map in all_path_nodes)
    )

    assert record_map_one == record_map_two == record_map_three

    with pytest.raises(PathChainMapError) as excinfo:
        _ = PathChainMap._resolve_record_maps(1)

    assert ("Expected either a PathRecordMap or a list of nodes to resolve into "
            f"a record map, Received element of type {type(1)}") in str(excinfo.value)

def test_path_record_index():
    path_string = '1.2.3'
    path = ProcessingPath(path_string)
    assert PathChainMap._path_record_index(path_string) == path.record_index
    assert PathChainMap._path_record_index(path) == path.record_index

    invalid_path = {}
    with pytest.raises(InvalidProcessingPathError) as excinfo:
        _ = PathChainMap._path_record_index(invalid_path)

    assert (f"Could not extract a record path for value of class {type(invalid_path)}, "
            "Expected a ProcessingPath with a numeric value in the first component") in str(excinfo.value)




def test_filtering(all_path_nodes):
    mapping = PathChainMap()

    for record_map in all_path_nodes:
        mapping.update(record_map)

    assert len(mapping.nodes) == 40

    assert not mapping.filter(prefix=11)
    assert not mapping.filter(prefix="11")
    assert len(mapping.filter(prefix="2")) == 4

    sample_node = mapping.nodes[0]

    assert mapping.get(sample_node.path[0]) is not None
    assert sample_node.path in mapping

    assert len(mapping.nodes) == 40
    record_index = PathChainMap._path_record_index(sample_node.path)
    mapping.remove(sample_node.path)
    assert record_index in mapping and sample_node.path and sample_node.path not in mapping
    assert len(mapping.nodes) == 39

    with pytest.raises(PathNodeMapError) as excinfo:
        _ = mapping.filter({})
    assert f"Encountered an error filtering PathNodeMaps within the ChainMap" in str(excinfo.value)


def test_retrieval(all_path_nodes, default_mapping):

    assert all(default_mapping.retrieve(path) for record in all_path_nodes for path in record)
    assert all(default_mapping.node_exists(node) for record in all_path_nodes for node in record.values())
    assert all(default_mapping.node_exists(node.path) for record in all_path_nodes for node in record.values())

    with pytest.raises(InvalidPathNodeError) as excinfo:
        _ = default_mapping.node_exists('')
    assert f"Key must be node or path. Received '{type('')}'" in str(excinfo.value)

def test_node_validation(all_path_nodes):

    record_map_two = PathRecordMap(record_index = 2)

    with pytest.raises(PathNodeMapError) as excinfo:
        _ = record_map_two.update(*(node for record in all_path_nodes for node in record.values()))

    assert ("Expected the first element in the path of the node to be the same type as the record index "
            "of the current PathRecordMap") in str(excinfo.value)

def test_contains(default_mapping):
    assert '1100' not in default_mapping
    assert None not in default_mapping
    assert '0'  in default_mapping
    assert 0  in default_mapping
    assert ProcessingPath('0') in default_mapping

    idx = len(default_mapping)
    assert idx and idx -1 in default_mapping

    first_node = default_mapping.nodes[0]

    assert first_node in default_mapping
    assert first_node.path in default_mapping
    assert first_node.path[:-1] / 'non-existent value' not in default_mapping
