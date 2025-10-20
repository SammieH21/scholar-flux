import pytest
from pydantic import ValidationError
from scholar_flux.api.models import PageListInput


def test_simple_page_list():
    """Test whether the PageListInput pydantic base-model validates and formats page numbers 1, 2, and 3."""
    pages = [1, 2, 3]
    page_list_input = PageListInput(pages)
    assert repr(page_list_input) == "PageListInput(1, 2, 3)"
    assert pages == list(page_list_input.page_numbers)


def test_singular_page():
    """Test whether, when a singular page number is entered, the page number is nested in a list."""
    pages = 5
    page_list_input = PageListInput(pages)  # type:ignore
    assert list(page_list_input.page_numbers) == [pages]


def test_singular_large_page():
    """Test a large page number: This method should work, whether for a small number, or an abnormally large page
    number."""
    pages = 50000000
    page_list_input = PageListInput(pages)  # type:ignore
    assert list(page_list_input.page_numbers) == [pages]


def test_singular_str():
    """A single or multi-digit should be coerced into a single integer value when possible."""
    pages = "12"
    page_list_input = PageListInput(pages)  # type:ignore
    assert list(page_list_input.page_numbers) == [int(pages)]


def test_empty_page_list():
    """Ensures that an empty page list input returns and empty list from its property."""
    page_list_input = PageListInput([])  # type:ignore
    assert list(page_list_input.page_numbers) == []


def test_sorted_page_list():
    """Page numbers should be automatically sorted in ascending order when provided out of order."""
    pages = [5, 2, 1]
    page_list_input = PageListInput(pages)
    assert list(reversed(pages)) == list(page_list_input.page_numbers)


def test_zero_indexed_page_list():
    """Tests whether 0 is treated as a valid page number.

    A zero indexed page should be allowed and handled only at the parameter building steps which will determine whether
    page=0 should be allowed given the parameter configuration for the current API Provider

    """
    pages = [0, 1, 2]
    page_list_input = PageListInput(pages)
    assert list(page_list_input.page_numbers) == pages


def test_ranged_page_list():
    """Ensures that the page numbers can be defined by a range."""
    pages = range(5)
    page_list_input = PageListInput(pages)
    assert list(page_list_input.page_numbers) == list(pages)


def test_mixed_types():
    """Tests whether the PageListInput class successfully converts lists with strings to a list of integers."""
    pages = ["00", 1, 2, 3, "10"]
    page_list_input = PageListInput(pages)  # type:ignore
    assert list(page_list_input.page_numbers) == sorted(int(page) for page in pages)  # type:ignore


def test_invalid_inputs(caplog):
    """Tests whether inputs that include invalid page numbers will raise an error as intended.

    Floats are flagged rather than coerced, and non-numeric strings should also raise errors.

    """
    with pytest.raises(ValidationError):
        # floats in are invalid and PageListInput errors as a result
        _ = PageListInput([1.2, 3.4, 5.6])  # type:ignore
    assert "Expected a provided page value to be a number. Received: '1.2'" in caplog.text

    invalid_function = map
    with pytest.raises(ValidationError):
        # the PageListInput model shouldn't accept functions as input
        _ = PageListInput(invalid_function)  # type:ignore
    assert (
        f"Expected a list, set, or generator containing page numbers. Received: '{type(invalid_function)}'"
        in caplog.text
    )

    invalid_string = "this is also invalid"
    with pytest.raises(ValidationError):
        # should initialize due to a wrong type (non-numeric strings)
        _ = PageListInput(invalid_string)  # type:ignore
    assert f"Expected a provided page value to be a number. Received: '{invalid_string}'" in caplog.text
