import pytest
from scholar_flux.utils.data_processing_utils import (RecursiveDictProcessor, KeyDiscoverer,
                                                      KeyFilter, PathUtils, JsonNormalizer)

# --- PathUtils Tests ---

@pytest.mark.parametrize("level_names,expected", [
    ([], ""),
    ([1, 2, 3], "1.2.3"),
    (["foo", 2, 3], "foo"),
    ([2, "bar"], "bar"),
])
def test_path_name(level_names, expected):
    assert PathUtils.path_name(level_names) == expected

def test_path_str():
    assert PathUtils.path_str(["a", 1, "b"]) == "a.1.b"

def test_remove_path_indices():
    assert PathUtils.remove_path_indices(["a", 1, "b", "value", 2]) == ["a", "b"]

def test_constant_path_indices():
    assert PathUtils.constant_path_indices(["a", 1, "b", 2]) == ["a", "i", "b", "i"]

def test_group_path_assignments():
    assert PathUtils.group_path_assignments(["a", 1, "b"]) == "a.i.b"
    assert PathUtils.group_path_assignments([]) is None

# --- KeyFilter Tests ---

@pytest.fixture
def discovered_keys():
    return {
        "John Doe": ["user.profile.name"],
        "johndoe@example.com": ["user.profile.email"],
        "en-US": ["system.settings.language"],
        "access_log_20240707.txt": ["system.logs.access"],
        "Widget X": ["product.catalog.item123.name"],
        "$19.99": ["product.catalog.item456.price"]
    }

def test_filter_by_prefix(discovered_keys):
    filtered = KeyFilter.filter_keys(discovered_keys, prefix="John")
    assert filtered == {"John Doe": ["user.profile.name"]}

def test_filter_by_min_length(discovered_keys):
    filtered = KeyFilter.filter_keys(discovered_keys, min_length=3)
    assert filtered == discovered_keys

def test_filter_by_substring(discovered_keys):
    filtered = KeyFilter.filter_keys(discovered_keys, substring="catalog")
    assert filtered == {
        "Widget X": ["product.catalog.item123.name"],
        "$19.99": ["product.catalog.item456.price"]
    }

def test_filter_by_pattern(discovered_keys):
    filtered = KeyFilter.filter_keys(discovered_keys, pattern=r"[a-z]+\d+")
    assert filtered == {
        "Widget X": ["product.catalog.item123.name"],
        "$19.99": ["product.catalog.item456.price"]
    }

def test_filter_with_multiple_criteria(discovered_keys):
    filtered = KeyFilter.filter_keys(
        discovered_keys, substring="product.catalog.item123", min_length=4, prefix="19"
    )
    assert filtered == {
        "Widget X": ["product.catalog.item123.name"],
        "$19.99": ["product.catalog.item456.price"]
    }

def test_filter_with_include_false(discovered_keys):
    filtered = KeyFilter.filter_keys(discovered_keys, substring="product", include_matches=False)
    assert filtered == {
        "John Doe": ["user.profile.name"],
        "johndoe@example.com": ["user.profile.email"],
        "en-US": ["system.settings.language"],
        "access_log_20240707.txt": ["system.logs.access"]
    }

# --- KeyDiscoverer Tests ---

@pytest.fixture
def sample_json():
    return {
        "name": "John",
        "address": {
            "street": "123 Maple Street",
            "city": "Springfield",
            "state": "IL"
        },
        "phones": [
            {"type": "home", "number": "123-456-7890"},
            {"type": "work", "number": "098-765-4321"}
        ]
    }

def test_key_discoverer_get_all_keys(sample_json):
    expected_keys = {
        'name': ['name'],
        'address': ['address'],
        'street': ['address.street'],
        'city': ['address.city'],
        'state': ['address.state'],
        'phones': ['phones'],
        'type': ['phones.0.type', 'phones.1.type'],
        'number': ['phones.0.number', 'phones.1.number']
    }
    kd = KeyDiscoverer([sample_json])
    assert kd.get_all_keys() == expected_keys

def test_key_discoverer_terminal_keys(sample_json):
    kd = KeyDiscoverer([sample_json])
    terminal_keys = kd.get_terminal_keys()
    assert set(terminal_keys.keys()) == {'name', 'street', 'city', 'state', 'type', 'number'}

def test_key_discoverer_terminal_paths(sample_json):
    kd = KeyDiscoverer([sample_json])
    paths = kd.get_terminal_paths()
    assert all(isinstance(p, str) for p in paths)
    assert 'name' in [p for p in paths if 'name' in p]

def test_key_discoverer_keys_with_path(sample_json):
    kd = KeyDiscoverer([sample_json])
    assert kd.get_keys_with_path('type') == ['phones.0.type', 'phones.1.type']
    assert kd.get_keys_with_path('missing') == []

def test_key_discoverer_filter_keys(sample_json):
    kd = KeyDiscoverer([sample_json])
    filtered = kd.filter_keys(prefix="name")
    assert filtered == {'name': ['name']}

# --- RecursiveDictProcessor Tests ---

def test_flatten_json(sample_json):
    expected_flattened = {
        'name': 'John',
        'street': '123 Maple Street',
        'city': 'Springfield',
        'state': 'IL',
        'type': ['home','work'],
        'number': ['123-456-7890','098-765-4321'],
    }
    processor = RecursiveDictProcessor(sample_json)
    flattened_json = processor.process_dictionary().flatten()
    assert flattened_json == expected_flattened

def test_combine_normalized():
    sample_json = {
        "name": "John",
        "bio": ["Developer", "Pythonista", "OpenAI enthusiast"]
    }
    processor = RecursiveDictProcessor(sample_json, normalizing_delimiter=None, object_delimiter='; ')
    flattened_json = processor.process_dictionary().flatten()
    expected_flattened = {
        'name': 'John',
        'bio': 'Developer; Pythonista; OpenAI enthusiast'
    }
    assert flattened_json == expected_flattened

def test_filter_extracted():
    sample_json = {
        "name": "John",
        "age": 30,
        "city": "Springfield"
    }
    processor = RecursiveDictProcessor(sample_json)
    processor.process_dictionary()
    processor.filter_extracted(exclude_keys=["age"])
    flattened = processor.flatten()
    assert flattened and "age" not in flattened

def test_process_and_flatten():
    sample_json = {
        "name": "John",
        "age": 30,
        "city": "Springfield"
    }
    processor = RecursiveDictProcessor()
    result = processor.process_and_flatten(sample_json, exclude_keys=["age"])
    assert result and "age" not in result

def test_unlist():
    assert RecursiveDictProcessor.unlist([{"a": 1}]) == {"a": 1}
    assert RecursiveDictProcessor.unlist([1, 2]) == [1, 2]
    assert RecursiveDictProcessor.unlist({"a": 1}) == {"a": 1}

def test_process_dictionary_raises():
    processor = RecursiveDictProcessor()
    with pytest.raises(ValueError):
        processor.process_dictionary()

# --- JsonNormalizer Tests ---

def test_json_normalizer_with_nested_dicts():
    sample_json = {
        "users": [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ],
        "meta": {"count": 2}
    }
    # Simulate RecursiveDictProcessor extraction
    processor = RecursiveDictProcessor(sample_json)
    processor.process_dictionary()
    extracted_data = [obj['data'] for obj in processor.json_extracted]
    extracted_paths = [obj['path'] for obj in processor.json_extracted]

    # Should produce:
    # extracted_data = ["Alice", "alice@example.com", "Bob", "bob@example.com", 2]
    # extracted_paths = [["users", 0, "name"], ["users", 0, "email"], ["users", 1, "name"], ["users", 1, "email"], ["meta", "count"]]

    normalizer = JsonNormalizer(extracted_data, extracted_paths)
    result = normalizer.normalize_extracted()

    # Expected: keys are 'users.name', 'users.email', 'meta.count'
    # Values are lists of corresponding data
    assert result == {'name': ['Alice', 'Bob'], 'email': ['alice@example.com', 'bob@example.com'], 'count': [2]}


def test_recursive_dict_with_path_collisions():
    sample_json = {
        "users": [
            {"name": "Alice", "email": "alice@example.com", 'car':{'brand': {'name':'Nissan', 'year':2014}}},
            {"name": "Bob", "email": "bob@example.com"}
        ],
        "meta": {"count": 2}
    }

    expected = {'name': ['Alice', 'Bob'], 'email': ['alice@example.com', 'bob@example.com'], 'brand.name': 'Nissan', 'year': 2014, 'count': 2}

    # Simulate RecursiveDictProcessor extraction
    processor = RecursiveDictProcessor(sample_json)
    flattened_dict = processor.process_and_flatten()

    # Expected: keys are 'users.name', 'users.email', 'meta.count'
    # Values are lists of corresponding data
    assert flattened_dict == expected


    processor_two = RecursiveDictProcessor(sample_json)

    processor_two.process_dictionary()
    extracted_data = [obj['data'] for obj in processor_two.json_extracted]
    extracted_paths = [obj['path'] for obj in processor_two.json_extracted]

    normalizer = JsonNormalizer(extracted_data, extracted_paths)
    result = normalizer.normalize_extracted()

    assert {k: (v[0] if isinstance(v, list) and len(v) == 1 else v) for k, v in result.items()} == expected 
