import re
from scholar_flux import DataExtractor
from scholar_flux.utils import (
    PathSimplifier,
    PathDiscoverer,
    PathNode,
    PathNodeMap,
    RecordPathNodeMap,
    PathNodeIndex,
    RecordPathChainMap,
    ProcessingPath,
)
import pytest


@pytest.fixture
def extracted_records(mock_academic_json):
    """Extracts valid records from the `mock_academic_json` for further testing using a list of dictionary records."""
    extractor = DataExtractor()
    records, _ = extractor.extract(mock_academic_json)
    return records


@pytest.fixture
def path_nodes(extracted_records):
    """Uses the extracted records to generate a set of path-value pairs for further testing."""
    path_discoverer = PathDiscoverer(extracted_records)
    path_dict = path_discoverer.discover_path_elements() or {}
    path_nodes = {PathNode(path, value) for path, value in path_dict.items()}
    return path_nodes


def test_index_mapping_validation(extracted_records):
    """Tests whether the method that creates and/or validates node mappings in a PathNodeIndex correctly prepares both
    RecordPathChainMap and PathNodeMaps.

    Independent of the modality that prepares the mappings, each should
    contain the same range of nodes when comparing the list of nodes
    within each mapping.
    """
    path_discoverer = PathDiscoverer(extracted_records)
    path_dict = path_discoverer.discover_path_elements()
    assert path_dict is not None
    path_node_dict = {path: PathNode(path, value) for path, value in path_dict.items()}

    mappings = PathNodeMap(path_node_dict)
    index1 = PathNodeIndex._validate_index(mappings)
    assert isinstance(index1, PathNodeMap)
    index2 = PathNodeIndex._validate_index(path_node_dict)
    assert isinstance(index2, PathNodeMap)
    assert index1 == index2

    chain_map = RecordPathChainMap(*path_node_dict.values())
    index3 = PathNodeIndex._validate_index(chain_map)

    assert index1.nodes == index2.nodes == index3.nodes


def test_chain_map_creation(path_nodes):
    """Validates whether the creation of a chain map with an iterable of nodes correctly instantiates a new
    RecordPathChainMap.

    The final chain map should include the full range of nodes from the
    `path_nodes` fixture.
    """
    assert path_nodes
    chain_map = RecordPathChainMap(*path_nodes)

    path_node_index = PathNodeIndex(chain_map)
    assert isinstance(path_node_index, PathNodeIndex) and isinstance(path_node_index.node_map, RecordPathChainMap)
    assert path_node_index.node_map == chain_map

    assert all(isinstance(record_mapping, RecordPathNodeMap) for record_mapping in path_node_index.node_map.values())

    assert len(path_node_index.node_map.nodes) == len(path_nodes) and all(
        node in path_nodes for node in path_node_index.node_map.nodes
    )


def test_map_method_equality(path_nodes):
    """Tests whether the instantiation and processing of PathNodeMaps and RecordPathChainMaps correctly processes and
    flattens both PathNodeMaps and RecordPathChainMaps in an identical manner."""
    map1 = PathNodeMap(*path_nodes)
    map2 = RecordPathChainMap(*path_nodes)
    assert sorted(map1.nodes) == sorted(map2.nodes)

    index1 = PathNodeIndex(map1)
    index2 = PathNodeIndex(map2)

    assert index1.simplify_to_rows() == index2.simplify_to_rows()


def test_path_node_index_from_path_mappings_and_search():
    """validates whether the use of path node indices correctly retrieves and searches relevant nodes."""
    mappings = {ProcessingPath(["0", "data", "0", "title"]): "A"}
    path_node_index = PathNodeIndex.from_path_mappings(mappings)
    retrieved_index = path_node_index.get_node(ProcessingPath(["0", "data", "0", "title"]))
    assert retrieved_index and retrieved_index.value == "A"
    searched_index = path_node_index.search(ProcessingPath(["0", "data"]))[0]
    assert searched_index and searched_index.value == "A"


def test_path_node_index_pattern_search_and_combine_keys():
    """Tests the simplifier to Verify that combining keys works as intended.

    When combining paths containing categories and their corresponding
    counts in two separate nodes, the category name is extracted from
    the `category` node and appended to the path of a new node.
    Similarly, the `value` attribute in the new node originates from the
    value from the `count` node.
    """
    mappings = {
        ProcessingPath(["0", "data", "0", "values", "value"]): "X",
        ProcessingPath(["0", "data", "0", "values", "count"]): 5,
    }
    path_node_index = PathNodeIndex.from_path_mappings(mappings)
    found = path_node_index.pattern_search(r".*value$")
    assert any(n.value == "X" for n in found)
    path_node_index.combine_keys()
    assert len(path_node_index.node_map) == 1

    result = path_node_index.node_map.nodes[0]

    expected = PathNode.to_path_node(path="0.data.0.values.value.X.count", value=5)
    assert result == expected
    # After combine_keys, the count node should have a new path including the value


def test_path_simplifier_simplify_paths_and_rows():
    """Verifies that using the `PathSimplifier` correctly simplifies the names for each path using a maximum of two of
    last components in each path to format the path string where each value from the JSON can be found."""
    path = [ProcessingPath(["0", "data", str(i), "title"]) for i in range(3)]
    nodes = [PathNode(p, f"title_{i}") for i, p in enumerate(path)]
    node_groups: list[ProcessingPath | str] = [node.path_group for node in nodes]
    simplifier = PathSimplifier(delimiter=".")
    mapping = simplifier.simplify_paths(node_groups, max_components=2)
    assert all(isinstance(k, ProcessingPath) for k in mapping)
    row = simplifier.simplify_to_row(nodes, collapse=None)
    assert all(k in row for k in mapping.values())


def test_integration_flatten_and_simplify(mock_academic_json):
    """Tests that flattening the mocked json data set using PathDiscoverer and PathNodeIndex produces the intended
    result when manually applying the individual components that integrate to process the JSON into a list of
    dictionaries."""
    discoverer = PathDiscoverer(mock_academic_json["data"])
    path_mappings = discoverer.discover_path_elements()
    assert isinstance(path_mappings, dict)
    idx = PathNodeIndex.from_path_mappings(path_mappings)
    rows = idx.simplify_to_rows()
    assert isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
    assert len(rows) == 3  # Should match the number of articles in mock_academic_json['data']

    # Checks whether each row contains the expected keys (e.g., 'title', 'doi', etc.)
    for row in rows:
        assert any("title" in k for k in row)
        assert any("doi" in k for k in row)


def test_index_parallel_normalization(extracted_records, caplog):
    """Validates whether index normalization correctly operates in parallel using multiprocessing."""
    assert isinstance(extracted_records, list)
    normalized_records = PathNodeIndex.normalize_records(extracted_records, parallel=True)
    assert isinstance(normalized_records, list) and all(isinstance(r, dict) and len(r) > 0 for r in normalized_records)
    assert re.search(r"Discovered [0-9]+ terminal paths", caplog.text) is not None

    assert "Created path index successfully from the provided path mappings" in caplog.text
    assert "Combining keys.." in caplog.text
    assert f"Successfully normalized {len(normalized_records)} records" in caplog.text
