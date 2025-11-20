from scholar_flux.utils import (
    PathSimplifier,
    PathDiscoverer,
    PathNode,
    PathNodeIndex,
    ProcessingPath,
)
import pytest


def test_path_uniqueness():
    """Verifies edge cases in the path simplification and flattening of data structures with redundant names.

    Paths should be handled predictably without the need to use indexes if it can be helped. The path simplifier
    will attempt to find the shortest available name that satisfies uniqueness if possible.

    """
    record_list: list[dict] = [
        {
            "colleague": {"author": [{"name": "Dr. Watts"}]},
            "author": {"name": "Dr. Lena"},
            "name": "Scholarly Works (1988)",
        },
        {"author": {"name": "Dr. Edgar"}, "name": "Quantum Thoughts (2023)"},
    ]
    path_mappings = PathDiscoverer(record_list).discover_path_elements() if isinstance(record_list, list) else {}
    assert path_mappings
    path_node_index = PathNodeIndex.from_path_mappings(path_mappings)
    assert path_node_index
    simplified_data = path_node_index.simplify_to_rows(max_components=3)
    assert [
        {"name": "Scholarly Works (1988)", "author.name": "Dr. Lena", "colleague.author.name": "Dr. Watts"},
        {"name": "Quantum Thoughts (2023)", "author.name": "Dr. Edgar"},
    ] == simplified_data


def test_generate_base_name_valid():
    """Verifies whether `_generate_base_name` returns a valid ProcessingPath for a given path and max_components."""
    simplifier = PathSimplifier()
    path = ProcessingPath(["a", "b", "c"])
    result = simplifier._generate_base_name(path, 2)
    assert isinstance(result, ProcessingPath)


def test_generate_base_name_invalid():
    """Verifies that the `_generate_base_name` method raises an exception when given invalid input."""
    simplifier = PathSimplifier()
    with pytest.raises(Exception):
        simplifier._generate_base_name("not_a_path", 2)  # type: ignore


def test_handle_collision_adds_suffix():
    """Verifies that `_handle_collision` will append a numeric suffix to resolve name collisions."""
    simplifier = PathSimplifier()
    base = ProcessingPath(["a", "b"])
    simplifier.name_mappings[base] = str(base)
    # Simulate collision
    result = simplifier._handle_collision(base)
    assert str(result).endswith("_1")


def test_generate_unique_name_no_collision():
    """Tests that `generate_unique_name` creates a valid name when no collision exists."""
    simplifier = PathSimplifier()
    path = ProcessingPath(["x", "y", "z"])
    name = simplifier.generate_unique_name(path, max_components=2)
    assert isinstance(name, ProcessingPath)
    assert ProcessingPath(["y", "z"]) == name


def test_generate_unique_name_with_collision():
    """Verifies whether `generate_unique_name` handles collisions by finding alternative unique names."""
    simplifier = PathSimplifier()
    path1 = ProcessingPath(["y", "z"])
    path2 = ProcessingPath(["x", "y", "z"])
    simplifier.name_mappings[path1] = str(path1)
    name = simplifier.generate_unique_name(path2, max_components=2)
    # When ['y', 'z'] is taken, it should either use the full path or add a suffix
    assert isinstance(name, ProcessingPath)
    assert name != path1  # Should not be identical to the existing mapping
    # Either uses full path or adds collision suffix
    assert str(name) == "x.y.z" or str(name).endswith("_1")


def test_simplify_paths_basic():
    """Test basic path simplification with multiple paths."""
    simplifier = PathSimplifier()
    paths = [ProcessingPath(["a", "b", "c"]), ProcessingPath(["a", "b", "d"])]
    mapping = simplifier.simplify_paths(paths, max_components=1)  # type: ignore
    assert all(isinstance(k, ProcessingPath) for k in mapping)


def test_simplify_paths_empty():
    """Tests that `simplify_paths` handles an empty path list correctly."""
    simplifier = PathSimplifier()
    mapping = simplifier.simplify_paths([], max_components=1)
    assert mapping == {}


def test_simplify_to_row_basic():
    """Tests that `simplify_to_row` correctly maps `PathNode` instances to their simplified names."""
    simplifier = PathSimplifier()
    path = ProcessingPath(["a", "b", "c"])
    simplifier.name_mappings[path.group()] = "c"
    node = PathNode(path, "value")
    row = simplifier.simplify_to_row([node])
    assert "c" in row and row["c"] == ["value"] or row["c"] == "value"


def test_simplify_to_row_missing_mapping():
    """Verifies whether the `simplify_to_row` method raises an exception when a path has no mapping."""
    simplifier = PathSimplifier()
    path = ProcessingPath(["a", "b", "c"])
    node = PathNode(path, "value")
    with pytest.raises(Exception):
        simplifier.simplify_to_row([node])


def test_collapse_various_inputs():
    """Tests the `_collapse` helper method with various input types."""
    assert PathSimplifier._collapse(["a", "b"], ",") == "a,b"
    assert PathSimplifier._collapse([], ",") is None
    assert PathSimplifier._collapse("", ",") is None
    assert PathSimplifier._collapse(["x"], ",") == "x"


def test_clear_and_get_mapped_paths():
    """Tests the `get_mapped_paths` and `clear_mappings` utility methods."""
    simplifier = PathSimplifier()
    path = ProcessingPath(["a", "b"])
    simplifier.name_mappings[path] = "b"
    assert simplifier.get_mapped_paths()
    simplifier.clear_mappings()
    assert simplifier.get_mapped_paths() == {}
