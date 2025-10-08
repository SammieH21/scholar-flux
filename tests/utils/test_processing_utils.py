import pytest
from scholar_flux.utils.json_processing_utils import (
    RecursiveDictProcessor,
    KeyDiscoverer,
    KeyFilter,
    PathUtils,
    JsonNormalizer,
)
from scholar_flux.utils import unlist_1d

#################### PathUtils Tests #######################


@pytest.mark.parametrize(
    "level_names,expected",
    [
        ([], ""),
        ([1, 2, 3], "1.2.3"),
        (["foo", 2, 3], "foo"),
        ([2, "bar"], "bar"),
    ],
)
def test_path_name(level_names, expected):
    """Verifies that basic path string utility functions work as intended for lightweight processing of JSON path"""
    assert PathUtils.path_name(level_names) == expected


def test_path_str():
    """Validates that the conversion of a list into a period delimited string works as intended"""
    assert PathUtils.path_str(["a", 1, "b"]) == "a.1.b"


def test_remove_path_indices():
    """Validates whether the removal of path indices (sometimes necessary for grouping) produces the expected result"""
    assert PathUtils.remove_path_indices(["a", 1, "b", "value", 2]) == ["a", "b"]


def test_constant_path_indices():
    """Validates whether numeric values are successfully converted into the intended constant for grouping paths"""
    assert PathUtils.constant_path_indices(["a", 1, "b", 2]) == ["a", "i", "b", "i"]
    assert PathUtils.constant_path_indices(["a", 1, "b", 2], constant = 'x') == ["a", "x", "b", "x"]


def join_as_str(values: list[list[str]]) -> str:
    return '.'.join(str(v) for v in values)
def test_group_path_assignments():
    """
    Validates whether grouped path assignments returns the expected values after converting numeric values into strings
    and attempting to convert nested list elements (paths) into a string representation.
    """
    # each list within each group of lists indicates a path
    group_one = [['a', i, 'b'] for i in range(3)]
    group_two = [['b', i, 'c'] for i in range(3)]
    group_three = [['d', i, 'f'] for i in range(3)]

    # nest multiple groups in a single list
    groups = [group_one, group_two, group_three]

    # equivalent calculations to group each individual path after converting numeric values into constants
    grouped_paths = ['.'.join('i' if isinstance(value, int) else str(value) for value in path)
                     for group in groups for path in group]

    # each individual path should be calculated in a similar manner:
    assert [PathUtils.group_path_assignments(path) for group in groups for path in group] == grouped_paths

    # grouping path assignments for empty lists should result in a None type
    assert PathUtils.group_path_assignments([]) is None


#################### KeyFilter Tests #######################


@pytest.fixture
def discovered_keys():
    """
    Helper fixture designed to evaluate whether the identification of keys and their corresponding path values
    works as intended.
    """
    return {
        "John Doe": ["user.profile.name"],
        "johndoe@example.com": ["user.profile.email"],
        "en-US": ["system.settings.language"],
        "access_log_20240707.txt": ["system.logs.access"],
        "Widget X": ["product.catalog.item123.name"],
        "$19.99": ["product.catalog.item456.price"],
    }


def test_filter_by_prefix(discovered_keys):
    """
    The keys in this scenario represents the terminal value within each path while each list represents the necessary
    path taken to find the value. Using the prefix, the path is identifiable.
    """
    filtered = KeyFilter.filter_keys(discovered_keys, prefix="John")
    assert filtered == {"John Doe": ["user.profile.name"]}


def test_filter_by_min_length(discovered_keys):
    """
    Validates whether the length of each list of discovered paths can be used to efficiently identify values with
    paths of a specific depth (min_length).
    """
    filtered = KeyFilter.filter_keys(discovered_keys, min_length=3)
    assert filtered == discovered_keys


def test_filter_by_substring(discovered_keys):
    """Verifies that attempts to filter paths using substring names operates as intended"""
    filtered = KeyFilter.filter_keys(discovered_keys, substring="catalog")
    assert filtered == {"Widget X": ["product.catalog.item123.name"], "$19.99": ["product.catalog.item456.price"]}


def test_filter_by_pattern(discovered_keys):
    """Verifies whether regex pattern matching correctly identifies paths with matching components"""
    filtered = KeyFilter.filter_keys(discovered_keys, pattern=r"[a-z]+\d+")
    assert filtered == {"Widget X": ["product.catalog.item123.name"], "$19.99": ["product.catalog.item456.price"]}


def test_filter_with_multiple_criteria(discovered_keys):
    """Validates that filtering paths and terminal values based on multiple matching criteria operates as expected"""
    filtered = KeyFilter.filter_keys(discovered_keys, substring="product.catalog.item123", min_length=4, prefix="19")
    assert filtered == {"Widget X": ["product.catalog.item123.name"], "$19.99": ["product.catalog.item456.price"]}


def test_filter_with_include_false(discovered_keys):
    """
    Verifies that using `include_matches=False` successfully removes matches from the final list of filtered value-path
    pairs.
    """
    filtered = KeyFilter.filter_keys(discovered_keys, substring="product", include_matches=False)
    assert filtered == {
        "John Doe": ["user.profile.name"],
        "johndoe@example.com": ["user.profile.email"],
        "en-US": ["system.settings.language"],
        "access_log_20240707.txt": ["system.logs.access"],
    }


#################### KeyDiscoverer Tests #######################


@pytest.fixture
def sample_json():
    """Fixture used to test the identification of keys and corresponding paths with nested components"""
    return {
        "name": "John",
        "address": {"street": "123 Maple Street", "city": "Springfield", "state": "IL"},
        "phones": [{"type": "home", "number": "123-456-7890"}, {"type": "work", "number": "098-765-4321"}],
    }


def test_key_discoverer_get_all_keys(sample_json):
    """
    Tests whether key-path identification via the `KeyDiscoverer` occurs as intended to identify path taken
    to arrive at nested values.

    For nested json data with multiple nested components, the identified key indicates the 
    name of the last key of a particular terminal path while the value represents the traversed paths taken
    to arrive at that key.
    """
    expected_keys = {
        "name": ["name"],
        "address": ["address"],
        "street": ["address.street"],
        "city": ["address.city"],
        "state": ["address.state"],
        "phones": ["phones"],
        "type": ["phones.0.type", "phones.1.type"],
        "number": ["phones.0.number", "phones.1.number"],
    }
    kd = KeyDiscoverer([sample_json])
    assert kd.get_all_keys() == expected_keys


def test_key_discoverer_terminal_keys(sample_json):
    """Verifies that the key discoverer can similarly identify terminal keys even when the json is nested in a list"""
    kd = KeyDiscoverer([sample_json])
    terminal_keys = kd.get_terminal_keys()
    assert set(terminal_keys.keys()) == {"name", "street", "city", "state", "type", "number"}


def test_key_discoverer_terminal_paths(sample_json):
    """
    Validates whether discovered terminal paths consist of a list of strings where each list represents the same
    set of keys found under a particular name, except with a different index used to traverse lists that arrive
    at a value with the same keys for example,  {'b': ['a.1.b', 'a.2.b', 'a.3.b']}, etc.

    The type for all terminal paths are verified to determine whether this is the case for all discovered keys.
    """

    kd = KeyDiscoverer([sample_json])
    paths = kd.get_terminal_paths()
    assert all(isinstance(p, str) for p in paths)
    assert "name" in [p for p in paths if "name" in p]


def test_key_discoverer_keys_with_path(sample_json):
    """Validates that the paths identified in the sample json fixture successfully match the actual observed paths"""
    kd = KeyDiscoverer([sample_json])
    assert kd.get_keys_with_path("type") == ["phones.0.type", "phones.1.type"]
    assert kd.get_keys_with_path("missing") == []


def test_key_discoverer_filter_keys(sample_json):
    """
    Verifies whether using `filter_keys` results in the expected value when the `KeyFilter` is called from 
    the current `KeyDiscoverer`.
    """
    kd = KeyDiscoverer([sample_json])
    filtered = kd.filter_keys(prefix="name")
    assert filtered == {"name": ["name"]}


################# RecursiveDictProcessor Tests ##################


def test_flatten_json(sample_json):
    """
    Verifies whether the RecursiveDictProcessor, created fromm each of the above tested classes, will successfully
    parse and flatten the sample json data as intended.

    `process_dictionary` is used to take a dictionary (or a single nested dictionary in a list of dictionaries))
    to process and subsequently flatten the result.
    """
    expected_flattened = {
        "name": "John",
        "street": "123 Maple Street",
        "city": "Springfield",
        "state": "IL",
        "type": ["home", "work"],
        "number": ["123-456-7890", "098-765-4321"],
    }
    processor = RecursiveDictProcessor(sample_json)
    flattened_json = processor.process_dictionary().flatten()
    assert flattened_json == expected_flattened


def test_combine_normalized():
    """
    Validates whether an attempt to combine normalized components from a sample JSON will combine each component
    as intended. If specified, the object delimiter should be used to successfully join lists into a single string
    where applicable.
    """
    sample_json = {"name": "John", "bio": ["Developer", "Pythonista", "OpenAI enthusiast"], "experience": {"testing": None}}
    processor = RecursiveDictProcessor(sample_json, normalizing_delimiter=None, object_delimiter="; ")
    flattened_json = processor.process_dictionary().flatten()
    expected_flattened = {"name": "John", "bio": "Developer; Pythonista; OpenAI enthusiast", "testing": None}
    assert flattened_json == expected_flattened
    processor.use_full_path = True
    flattened_json_two  = processor.process_dictionary().flatten()
    expected_flattened_two = {"name": "John", "bio": "Developer; Pythonista; OpenAI enthusiast", "experience.testing": None}
    assert flattened_json_two == expected_flattened_two


def test_filter_extracted():
    """Validates whether the processed and flattened components of the dictionary can be successfully filtered"""
    sample_json = {"name": "John", "age": 30, "city": "Springfield"}
    processor = RecursiveDictProcessor(sample_json)
    processor.process_dictionary()
    processor.filter_extracted(exclude_keys=["age"])
    flattened = processor.flatten()
    assert flattened and "age" not in flattened


def test_process_and_flatten():
    """
    Validates the capability and output of the RecursiveDictProcessor when processing and flattening a sample JSON.

    The final result should be a list of keys that contains all items other than `age` which should be excluded
    from the final output.
    """
    sample_json = {"name": "John", "age": 30, "city": "Springfield"}
    processor = RecursiveDictProcessor()
    result = processor.process_and_flatten(sample_json, exclude_keys=["age"])
    assert isinstance(result, dict)
    # all keys/values found in the sample json should be available unless the checked key is age which was removed
    assert all((key in result and value == result[key]) ^ (key == 'age') for key, value in sample_json.items())


def test_unlist():
    """Verifies that unlisting a list containing an singular element of any type extracts that element"""
    assert RecursiveDictProcessor.unlist([{"a": 1}]) == {"a": 1}
    assert RecursiveDictProcessor.unlist([1, 2]) == [1, 2]
    assert RecursiveDictProcessor.unlist({"a": 1}) == {"a": 1}


def test_process_dictionary_raises():
    """
    Verifies that attempting to process a dictionary without input will raise a value error if
    data was neither specified on instantiation nor when calling `process_dictionary`
    """
    processor = RecursiveDictProcessor()
    with pytest.raises(ValueError):
        processor.process_dictionary()


#################### JsonNormalizer Tests ###################

def test_json_normalizer_with_nested_dicts():
    """
    Validates that processing dictionaries with nested components with the RecursiveDictProcessor
    will return the processed result that maps the names of terminal to the paths where the unique terminal path
    keys can be located.
    """
    sample_json = {
        "users": [{"name": "Alice", "email": "alice@example.com"}, {"name": "Bob", "email": "bob@example.com"}],
        "meta": {"count": 2},
    }

    # Simulate RecursiveDictProcessor extraction
    processor = RecursiveDictProcessor(sample_json)
    processor.process_dictionary()

    # manually extracts the data at the end of the path and the path where the data can be found
    json_record_data = processor.extracted_record_data_list

    # Should produce:
    # extracted_data = ["Alice", "alice@example.com", "Bob", "bob@example.com", 2]
    # extracted_paths = [["users", 0, "name"], ["users", 0, "email"], ["users", 1, "name"], ["users", 1, "email"], ["meta", "count"]]

    # normalizes a set of values (data) and their paths where each index corresponds to an extracted path and element
    normalizer = JsonNormalizer(json_record_data)
    result = normalizer.normalize_extracted()

    # Expected: keys are 'users.name', 'users.email', 'meta.count'
    # Values are lists of corresponding data
    assert result == {"name": ["Alice", "Bob"], "email": ["alice@example.com", "bob@example.com"], "count": [2]}


def test_recursive_dict_with_path_collisions():
    """
    Validates whether path collisions are accounted for when flattening path-data pairs with the same name of a
    terminal key at different groups of paths (as identified by replacing numeric values with a constant)

    When path collisions occur, the smallest name for a key that makes it distinguishable from another colliding key
    should be used.
    """
    sample_json = {
        "users": [
            {"name": "Alice", "email": "alice@example.com", "car": {"brand": {"name": "Nissan", "year": 2014}}},
            {"name": "Bob", "email": "bob@example.com"},
        ],
        "meta": {"count": 2},
    }

    # `name` and `brand.name` should be distinguishable in the final result
    expected = {
        "name": ["Alice", "Bob"],
        "email": ["alice@example.com", "bob@example.com"],
        "brand.name": "Nissan",
        "year": 2014,
        "count": 2,
    }

    # Simulate RecursiveDictProcessor extraction
    processor = RecursiveDictProcessor(sample_json)
    flattened_dict = processor.process_and_flatten()

    # Expected: keys are 'users.name', 'users.email', 'meta.count'
    # Values are lists of corresponding data
    assert flattened_dict == expected

    processor_two = RecursiveDictProcessor(sample_json)

    # Validating whether manual use of the path processor and JsonNormalizer results in the same output
    processor_two.process_dictionary()
    json_record_data = processor.extracted_record_data_list

    # identifies collisions and consolidates path names against what's available
    normalizer = JsonNormalizer(json_record_data)
    result = normalizer.normalize_extracted()

    # removes single elements from lists and validates the result against what's expected
    assert {k: unlist_1d(v) for k, v in result.items()} == expected
