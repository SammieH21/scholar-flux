from __future__ import annotations

from scholar_flux.exceptions.path_exceptions import (
    InvalidProcessingPathError,
    RecordPathNodeMapError,
    PathNodeMapError,
    RecordPathChainMapError,
    InvalidPathNodeError,
)
import pytest


from scholar_flux.utils.paths import ProcessingPath, PathNode, PathNodeMap, RecordPathNodeMap, RecordPathChainMap


@pytest.fixture
def all_path_nodes():
    """Fixture for mocking nodes from a single record."""
    all_path_nodes = []
    for i in range(10):
        idx = i
        path_nodes = [PathNode.to_path_node(f"{i}.a.{x}", i) for x in ("a", "b", "c", "d")]

        path_records = RecordPathNodeMap(*path_nodes, record_index=idx)
        all_path_nodes.append(path_records)
    return all_path_nodes


@pytest.fixture
def default_mapping(all_path_nodes):
    """Creates a ChainMap from the previously created fixture."""
    default_mapping = RecordPathChainMap(*all_path_nodes)
    return default_mapping


def test_blank_initialization():
    """Testing the initialization of a chainmap without arguments."""
    mapping = RecordPathChainMap()
    assert mapping == RecordPathChainMap({})  # type: ignore
    assert mapping == RecordPathChainMap(set())  # type: ignore
    assert mapping == RecordPathChainMap([])  # type: ignore
    assert mapping == RecordPathChainMap(tuple())  # type: ignore


def test_initialization(all_path_nodes):
    """Verifies whether the RecordPathChainMap will correctly initialize with the assigned records with the different
    configurations used to assign records to the mapping."""
    mapping = RecordPathChainMap()
    assert len(mapping) == 0

    for record_map in all_path_nodes:
        mapping[record_map.record_index] = record_map

    assert len(mapping) == 10
    assert len(mapping.nodes) == 40

    mapping_two = RecordPathChainMap(*all_path_nodes)
    assert mapping == mapping_two

    mapping_three = RecordPathChainMap()
    mapping_three.update(*all_path_nodes)

    assert mapping_three == mapping

    mapping_four = RecordPathChainMap()
    nodes = [node for node_map in all_path_nodes for node in node_map.values()]
    assert len({node.path for node in nodes}) == 40
    mapping_four.update(*(node for node_map in all_path_nodes for node in node_map.values()))

    assert len(mapping_four) == 10
    assert all(isinstance(path, RecordPathNodeMap) for path in mapping_four.data.values())
    assert len(mapping_four.nodes) == 40

    mapping_five = RecordPathChainMap()
    for node in nodes:
        mapping_five.add(node)
    assert mapping_five == mapping


def test_inferred_record_index():
    """Verifies whether not directly specifying a record_index throws an error or infers from the input nodes.

    Whenever a RecordPathNodeMap is specified with defaults, the index
    should be inferred from the first element of each path. An error is
    raised when encountering zero or more than one record_index.
    """
    a1 = PathNode.to_path_node("1.a", value=1)
    a2 = PathNode.to_path_node("1.b", value=2)
    a3 = PathNode.to_path_node("1.c", value=3)

    record_map = RecordPathNodeMap(a1, a2, a3)

    assert record_map.record_index == 1

    record_dict: dict = {str(a.path): a for a in (a1, a2, a3)}
    mapping = PathNodeMap()
    mapping.format_mapping(record_dict)
    record_map_two = RecordPathNodeMap(**record_dict)

    assert record_map_two.record_index == 1
    assert record_map_two == record_map

    with pytest.raises(RecordPathNodeMapError) as excinfo:
        _ = RecordPathNodeMap()
    assert "A numeric record index is missing and could not be inferred from the input nodes" in str(excinfo.value)

    with pytest.raises(InvalidPathNodeError) as excinfo:  # type: ignore
        _ = RecordPathNodeMap(" ")  # type: ignore
    assert f"The current object is not a PathNode: expected 'PathNode', received {type(' ')}" in str(excinfo.value)


def test_formatting(all_path_nodes):
    """Tests whether the helper function accommodates a the expected range of inputs including nodes and/or a
    sequence/mapping of nodes as intended."""
    positional_params = (node for record in all_path_nodes[5:] for node in record.values())
    keyword_params = {str(path): node for record in all_path_nodes[:5] for path, node in record.items()}

    assert positional_params
    assert keyword_params
    mapping = RecordPathChainMap()

    formatted_mappings = PathNodeMap._format_nodes_as_dict(*positional_params, **keyword_params)
    assert len(formatted_mappings) == 40

    mapping.update(*all_path_nodes)
    assert mapping.nodes == list(formatted_mappings.values())
    assert mapping.paths == list(formatted_mappings.keys())


def test_invalid_formatting():
    """Validates the `_format_nodes_as_dict` function by attempting to raise a PathNodeMapError by providing invalid
    inputs that should raise the exception.

    This test identifies whether non-nodes are successfully flagged and
    the appropriate exception raised.
    """
    new_path_node = RecordPathNodeMap(record_index=1)
    invalid_path_node = {"a": " "}
    with pytest.raises(PathNodeMapError) as excinfo:
        _ = new_path_node._format_nodes_as_dict(invalid_path_node)
    assert (
        "Could not format the input as a dictionary of nodes: Expected the input to be a "
        f"PathNode or sequence/mapping containing PathNodes. Instead received {type(invalid_path_node)}"
    ) in str(excinfo.value)


def test_record_map_creation():
    """Tests instantiation of a record map using several instantiation methods with a sequence/mapping of nodes.

    Each method should result in the same record map structure and not
    vary. We can consider a sequence of nodes to internally map a path
    to a node value.
    """
    a1 = PathNode.to_path_node("1.a", value=1)
    a2 = PathNode.to_path_node("1.b", value=2)
    a3 = PathNode.to_path_node("1.c", value=3)

    seq = [a1, a2, a3]

    mapping: dict = {a1.path: a1, a2.path: a2, a3.path: a3}

    # using a sequence
    record_map = RecordPathNodeMap.from_mapping(seq)

    # with a dictionary
    record_map_two = RecordPathNodeMap.from_mapping(mapping)
    assert len(record_map) == 3
    assert record_map == record_map_two
    record_map_three = RecordPathNodeMap.from_mapping(record_map_two)
    assert record_map_three == record_map_two

    # with a dictionary of length 1
    record_map_single = RecordPathNodeMap({a1.path: a1})
    assert len(record_map_single) == 1

    # with a single node
    assert record_map_single == RecordPathNodeMap(a1)

    # with a tuple containing a single node
    record_map_single_two = RecordPathNodeMap((a1,))

    # verifies whether the two methods are equal
    assert record_map_single == record_map_single_two

    # with a list containing a node
    record_map_single_three = RecordPathNodeMap([a1])
    assert record_map_single_three == record_map_single

    # with a set containing  node
    record_map_single_four = RecordPathNodeMap({a1})
    assert record_map_single_four == record_map_single


def test_chain_input_preparation():
    """Test robustness and equality of methods used to prepare node inputs for use in practice by testing
    `_prepare_inputs` with a range of both valid and invalid inputs."""
    a1 = PathNode.to_path_node("2.a", value=1)
    a2 = PathNode.to_path_node("2.b", value=2)
    a3 = PathNode.to_path_node("2.c", value=3)

    prepped_inputs = RecordPathNodeMap._prepare_inputs([a1, a2, a3])
    assert prepped_inputs == (2, [a1, a2, a3])

    prepped_inputs_two = RecordPathNodeMap._prepare_inputs([a1])
    assert prepped_inputs_two == (2, [a1])

    prepped_inputs_three = RecordPathNodeMap._prepare_inputs(a1)
    assert prepped_inputs_two == prepped_inputs_three

    bad_node = "not a node"

    with pytest.raises(RecordPathNodeMapError) as excinfo:
        _ = RecordPathNodeMap._prepare_inputs(bad_node)  # type: ignore
    assert (
        "Encountered an error on the preparation of inputs for a RecordPathNodeMap: "
        "The current object is not a PathNode"
    ) in str(excinfo.value)

    another_bad_node = 1100

    with pytest.raises(RecordPathNodeMapError) as excinfo:
        _ = RecordPathNodeMap._prepare_inputs(another_bad_node)  # type: ignore
    assert ("Expected a sequence of nodes, but at least one value is of a different type") in str(excinfo.value)


def test_invalid_record_indices():
    """Ensures invalid record indices are flagged as such: includes inputs with two different prefixes in path names."""
    a1 = PathNode.to_path_node("1.a", value=1)
    b1 = PathNode.to_path_node("2.g", value=3)

    with pytest.raises(RecordPathNodeMapError) as excinfo:
        _ = RecordPathNodeMap._prepare_inputs([a1, b1])
    assert ("Expected a mapping or sequence with exactly 1 record_index, " "Received: [1, 2]") in str(excinfo.value)


def test_record_map_resolution(all_path_nodes):
    """Validates whether each of the following methods produces the same output when generating record maps from
    mappings and lists using the `RecordPathChainMap._resolve_record_maps` method."""
    record_map_one = RecordPathChainMap._resolve_record_maps(*all_path_nodes)
    record_map_two = RecordPathChainMap._resolve_record_maps(
        *(node for node_map in all_path_nodes for node in node_map.values())
    )

    record_map_three = RecordPathChainMap._resolve_record_maps(*(PathNodeMap(node_map) for node_map in all_path_nodes))

    assert record_map_one == record_map_two == record_map_three

    with pytest.raises(RecordPathChainMapError) as excinfo:
        _ = RecordPathChainMap._resolve_record_maps(1)  # type: ignore

    assert (
        "Expected either a RecordPathNodeMap or a list of nodes to resolve into "
        f"a record map, Received element of type {type(1)}"
    ) in str(excinfo.value)


def test_extract_record_index():
    """Validates the record index calculation of record indices against valid and invalid inputs to determine whether
    each input produces the intended result and is consistent with the record indices that originate from individual
    paths."""
    path_string = "1.2.3"
    path = ProcessingPath(path_string)
    assert RecordPathChainMap._extract_record_index(path_string) == path.record_index
    assert RecordPathChainMap._extract_record_index(path) == path.record_index

    invalid_path: dict = {}
    with pytest.raises(InvalidProcessingPathError) as excinfo:
        _ = RecordPathChainMap._extract_record_index(invalid_path)  # type: ignore

    assert (
        f"Could not extract a record path for value of class {type(invalid_path)}, "
        "Expected a ProcessingPath with a numeric value in the first component"
    ) in str(excinfo.value)


def test_filtering(all_path_nodes):
    """Tests filtering against a range of both valid and invalid inputs to ensure that filtering correctly returns nodes
    matching a condition when valid inputs are received.

    Also verifies edge cases concerning invalid inputs and exceptions
    that can result with invalid inputs.
    """
    mapping = RecordPathChainMap()

    for record_map in all_path_nodes:
        mapping.update(record_map)

    assert len(mapping.nodes) == 40

    assert not mapping.filter(prefix=11)  # type: ignore
    assert not mapping.filter(prefix="11")  # type: ignore
    assert len(mapping.filter(prefix="2")) == 4  # type: ignore

    sample_node = mapping.nodes[0]

    assert mapping.get(sample_node.path[0]) is not None
    assert sample_node.path in mapping

    assert len(mapping.nodes) == 40
    record_index = RecordPathChainMap._extract_record_index(sample_node.path)
    mapping.remove(sample_node.path)
    assert record_index in mapping and sample_node.path and sample_node.path not in mapping
    assert len(mapping.nodes) == 39

    with pytest.raises(PathNodeMapError) as excinfo:
        _ = mapping.filter({})  # type: ignore
    assert "Encountered an error filtering PathNodeMaps within the ChainMap" in str(excinfo.value)


def test_retrieval(all_path_nodes, default_mapping):
    """Tests whether each source (the nodes used to create the mapping and the methods of the map) correctly identifies
    the same nodes using the `retrieve` method and the `node_exists` method with nodes and paths respectively.

    In contrast, a non-node/path should raise an error.
    """
    assert all(default_mapping.get_node(path) for record in all_path_nodes for path in record)
    assert all(default_mapping.node_exists(node) for record in all_path_nodes for node in record.values())
    assert all(default_mapping.node_exists(node.path) for record in all_path_nodes for node in record.values())

    with pytest.raises(InvalidPathNodeError) as excinfo:
        _ = default_mapping.node_exists("")  # type: ignore
    assert f"Key must be node or path. Received '{type('')}'" in str(excinfo.value)


def test_node_validation(all_path_nodes):
    """
    Verifies whether `update` validates the record node when the map is constrained to `record_index = 2`
    (as opposed to `record_index = 1`). In this scenario, an error should be raised when encountering
    the incorrect leading path component/record_index.
    """

    record_map_two = RecordPathNodeMap(record_index=2)

    with pytest.raises(PathNodeMapError) as excinfo:
        record_map_two.update(*(node for record in all_path_nodes for node in record.values()))

    assert (
        "Expected the first element in the path of the node to be the same type as the record index "
        "of the current RecordPathNodeMap"
    ) in str(excinfo.value)


def test_contains(default_mapping):
    """Verifies that key membership is operating as intended. Nodes, paths, and strings should first be coerced into
    paths and subsequently record_indexes to verify whether, first, the record_index exists associated with the path.

    If an actual path is specified instead of a record index, then
    membership testing will existing to the path and verify whether the
    associated path node exists.
    """
    assert "1100" not in default_mapping
    assert None not in default_mapping
    assert "0" in default_mapping
    assert 0 in default_mapping
    assert ProcessingPath("0") in default_mapping

    idx = len(default_mapping)
    assert idx and idx - 1 in default_mapping

    first_node = default_mapping.nodes[0]

    assert first_node in default_mapping
    assert first_node.path in default_mapping
    assert first_node.path[:-1] / "non-existent value" not in default_mapping
