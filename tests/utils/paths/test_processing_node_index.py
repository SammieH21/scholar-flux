import re
from scholar_flux import DataExtractor
from scholar_flux.utils import PathDiscoverer, PathNode, PathNodeMap, PathNodeIndex


def test_index_init(mock_academic_json, caplog):
    records, _ = DataExtractor().extract(mock_academic_json)
    path_discoverer = PathDiscoverer(records)
    path_dict = path_discoverer.discover_path_elements()
    assert path_dict is not None
    path_node_dict = {path: PathNode(path, value) for path, value in path_dict.items()}
    mappings = PathNodeMap(path_node_dict)

    index1 = PathNodeIndex._validate_index(mappings)
    assert isinstance(index1, PathNodeMap)
    index2 = PathNodeIndex._validate_index(path_node_dict)
    assert isinstance(index2, PathNodeMap)
    assert index1 == index2


def test_index_normalization(mock_academic_json, caplog):
    records, _ = DataExtractor().extract(mock_academic_json)
    assert isinstance(records, list)
    normalized_records = PathNodeIndex.normalize_records(records, parallel=True)
    assert isinstance(normalized_records, list) and all(isinstance(r, dict) for r in normalized_records)
    assert re.search(r"Discovered [0-9]+ terminal paths", caplog.text) is not None

    assert "Created path index successfully from the provided path mappings" in caplog.text
    assert "Combining keys.." in caplog.text
    assert f"Successfully normalized {len(normalized_records)} records" in caplog.text
