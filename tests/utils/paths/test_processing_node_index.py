import re
from scholar_flux import DataExtractor
from scholar_flux.utils import PathDiscoverer, PathNode, PathNodeMap, PathNodeIndex, PathRecordMap, PathChainMap
import pytest



@pytest.fixture
def extracted_records(mock_academic_json):
    extractor = DataExtractor()
    records, _ = extractor.extract(mock_academic_json)
    return records

@pytest.fixture
def path_nodes(extracted_records):
    path_discoverer = PathDiscoverer(extracted_records)
    path_dict = path_discoverer.discover_path_elements()  or {}
    path_nodes = {PathNode(path, value) for path, value in path_dict.items()}
    return path_nodes

def test_index_init(extracted_records, caplog):
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

    chain_map = PathChainMap(*path_node_dict.values())
    index3 = PathNodeIndex._validate_index(chain_map)
    assert index1.nodes == index2.nodes == index3.nodes

def test_chain_map_creation(path_nodes):

    assert path_nodes
    chain_map = PathChainMap(*path_nodes)

    path_node_index = PathNodeIndex(chain_map)
    assert isinstance(path_node_index, PathNodeIndex) and isinstance(path_node_index.index, PathChainMap)
    assert path_node_index.index == chain_map
    assert len(path_node_index.index.nodes ) == len(path_nodes) and \
            all(node in path_nodes for node in path_node_index.index.nodes)

def test_map_method_equality(path_nodes):
    map1 = PathNodeMap(*path_nodes)
    map2 = PathChainMap(*path_nodes)
    assert sorted(map1.nodes) == sorted(map2.nodes)

    index1 = PathNodeIndex(map1)
    index2 = PathNodeIndex(map2)

    assert index1.simplify_to_rows() == index2.simplify_to_rows()

def test_index_normalization(extracted_records, caplog):
    assert isinstance(extracted_records, list)
    normalized_records = PathNodeIndex.normalize_records(extracted_records, parallel=True)
    assert isinstance(normalized_records, list) and all(isinstance(r, dict) for r in normalized_records)
    assert re.search(r"Discovered [0-9]+ terminal paths", caplog.text) is not None

    assert "Created path index successfully from the provided path mappings" in caplog.text
    assert "Combining keys.." in caplog.text
    assert f"Successfully normalized {len(normalized_records)} records" in caplog.text 
