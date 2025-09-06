from scholar_flux.utils.paths import ProcessingPath, PathNode, PathNodeMap, PathNodeIndex, PathSimplifier, PathDiscoverer


def test_pathnode_creation_and_properties():
    path = ProcessingPath(['0', 'data', '0', 'title'])
    node = PathNode(path, "Correction: Mitochondrial flux impacts tumor cell survival under hypoxic conditions")
    assert node.path == path
    assert node.value.startswith("Correction")
    assert node.path_keys == ProcessingPath(['data', 'title'])
    assert node.path_group.components[-1] == 'i' or node.path_group.components[-1] == 'title'
    assert node.record_index == 0

def test_pathnode_update_and_equality():
    path = ProcessingPath(['0', 'data', '0', 'title'])
    node = PathNode(path, "A")
    updated = node.update(value="B")
    assert updated.value == "B"
    assert updated.path == node.path
    assert node != updated
    assert hash(node) == hash(node.path)

def test_pathnodemap_add_get_remove():
    path = ProcessingPath(['0', 'data', '0', 'title'])
    node = PathNode(path, "A")
    m = PathNodeMap()
    m.add(node)
    assert m.get(path) == node
    assert path in m
    m.remove(path)
    assert m.get(path) is None

def test_pathnodemap_filter_and_cache():
    m = PathNodeMap()
    nodes = [PathNode(ProcessingPath(['0', 'data', str(i), 'title']), f"title_{i}") for i in range(3)]
    for node in nodes:
        m.add(node)
    filtered = m.filter(ProcessingPath(['0', 'data']), min_depth=3)
    assert all(n.path in filtered for n in nodes)
    # Enable cache and test cache_filter
    m.cache = True
    filtered_cache = m.filter(ProcessingPath(['0', 'data']), from_cache=True)
    assert filtered_cache == filtered

def test_pathnodeindex_from_path_mappings_and_search():
    mappings = {ProcessingPath(['0', 'data', '0', 'title']): "A"}
    idx = PathNodeIndex.from_path_mappings(mappings)
    retrieved_index = idx.retrieve(ProcessingPath(['0', 'data', '0', 'title']))
    assert retrieved_index and retrieved_index.value == "A"
    searched_index = idx.search(ProcessingPath(['0', 'data']))[0]
    assert searched_index and searched_index.value == "A"

def test_pathnodeindex_pattern_search_and_combine_keys():
    mappings = {
        ProcessingPath(['0', 'data', '0', 'values', 'value']): "X",
        ProcessingPath(['0', 'data', '0', 'values', 'count']): 5
    }
    idx = PathNodeIndex.from_path_mappings(mappings)
    found = idx.pattern_search(r'.*value$')
    assert any(n.value == "X" for n in found)
    idx.combine_keys()
    assert len(idx.index) == 1
    # After combine_keys, the count node should have a new path including the value

def test_pathsimplifier_simplify_paths_and_rows():
    path = [ProcessingPath(['0', 'data', str(i), 'title']) for i in range(3)]
    nodes = [PathNode(p, f"title_{i}") for i, p in enumerate(path)]
    node_groups: list[ProcessingPath | str ] = [node.path_group for node in nodes]
    simplifier = PathSimplifier(delimiter='.')
    mapping = simplifier.simplify_paths(node_groups, max_components=2)
    assert all(isinstance(k, ProcessingPath) for k in mapping)
    row = simplifier.simplify_to_row(nodes, collapse=None)
    assert all(k in row for k in mapping.values())

def test_integration_flatten_and_simplify(mock_academic_json):
    # Flatten the fake JSON using PathDiscoverer and PathNodeIndex
    discoverer = PathDiscoverer(mock_academic_json['data'])
    path_mappings = discoverer.discover_path_elements()
    assert isinstance(path_mappings, dict)
    idx = PathNodeIndex.from_path_mappings(path_mappings)
    rows = idx.simplify_to_rows()
    assert isinstance(rows, list)
    assert len(rows) == 3  # Should match the number of articles in mock_academic_json['data']
    # Check that each row contains expected keys (e.g., 'title', 'doi', etc.)
    for row in rows:
        assert any('title' in k for k in row)
        assert any('doi' in k for k in row)
