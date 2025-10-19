from scholar_flux.data import DataProcessor, RecursiveDataProcessor, PathDataProcessor
from scholar_flux.utils import quote_if_string


def test_data_processor_repr():
    """Verifies the representation of the DataProcessor to ensure it shows in the terminal as intended."""
    processor = DataProcessor()

    value_delimiter = quote_if_string(processor.value_delimiter)
    record_keys = quote_if_string(processor.record_keys)
    ignore_keys = quote_if_string(processor.ignore_keys)
    keep_keys = quote_if_string(processor.keep_keys)
    regex = quote_if_string(processor.regex)

    expected = (
        f"DataProcessor(record_keys={record_keys},\n"
        f"              ignore_keys={ignore_keys},\n"
        f"              keep_keys={keep_keys},\n"
        f"              value_delimiter={value_delimiter},\n"
        f"              regex={regex})"
    )
    assert processor.__repr__() == expected


def test_path_data_processor_repr():
    """Verifies the representation of the PathDataProcessor in the CLI to determine whether it displays as intended."""
    processor = PathDataProcessor()

    value_delimiter = quote_if_string(processor.value_delimiter)
    ignore_keys = quote_if_string(processor.ignore_keys)
    keep_keys = quote_if_string(processor.keep_keys)

    expected = (
        f"PathDataProcessor(value_delimiter={value_delimiter},\n"
        f"                  regex=True,\n"
        f"                  ignore_keys={ignore_keys},\n"
        f"                  keep_keys={keep_keys},\n"
        f"                  path_node_index=PathNodeIndex(...))"
    )

    assert processor.__repr__() == expected


def test_recursive_data_processor_repr():
    """Verifies the representation of the RecursiveDataProcessor in the CLI to determine whether it displays as
    intended."""
    processor = RecursiveDataProcessor()

    value_delimiter = quote_if_string(processor.value_delimiter)
    ignore_keys = quote_if_string(processor.ignore_keys)
    keep_keys = quote_if_string(processor.keep_keys)
    regex = quote_if_string(processor.regex)
    use_full_path = quote_if_string(processor.recursive_processor.use_full_path)
    key_discoverer = quote_if_string(processor.key_discoverer)
    recursive_processor = quote_if_string(processor.recursive_processor)

    expected = (
        f"RecursiveDataProcessor(value_delimiter={value_delimiter},\n"
        f"                       ignore_keys={ignore_keys},\n"
        f"                       keep_keys={keep_keys},\n"
        f"                       regex={regex},\n"
        f"                       use_full_path={use_full_path},\n"
        f"                       key_discoverer={key_discoverer},\n"
        f"                       recursive_processor={recursive_processor})"
    )
    assert processor.__repr__() == expected
