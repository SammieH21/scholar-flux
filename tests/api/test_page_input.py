import pytest
from pydantic import ValidationError
from scholar_flux.api.models import PageListInput


def test_simple_page_list():
    pages = [1,2,3]
    page_list_input = PageListInput(pages)
    assert repr(page_list_input) == 'PageListInput(1, 2, 3)'
    assert pages == list(page_list_input.page_numbers)

def test_singular_page():
    pages = 5
    page_list_input = PageListInput(pages) #type:ignore
    assert list(page_list_input.page_numbers) == [pages]

def test_singular_large_page():
    pages = 50000000
    page_list_input = PageListInput(pages) #type:ignore
    assert list(page_list_input.page_numbers) == [pages]


def test_singular_str():
    pages = '12'
    page_list_input = PageListInput(pages) #type:ignore
    assert list(page_list_input.page_numbers) == [int(pages)]

def test_empty_page_list():
    page_list_input = PageListInput([]) #type:ignore
    assert list(page_list_input.page_numbers) == []


def test_sorted_page_list():
    pages = [5,2,1]
    page_list_input = PageListInput(pages)
    assert list(reversed(pages)) == list(page_list_input.page_numbers)

def test_zero_indexed_page_list(caplog):
    pages = [0, 1, 2]
    page_list_input = PageListInput(pages)
    assert list(page_list_input.page_numbers) == [1, 2]
    assert "Skipping the page number, 0, as it is not a valid page number." in caplog.text

def test_ranged_page_list(caplog):
    pages = range(5)
    page_list_input = PageListInput(pages)
    assert list(page_list_input.page_numbers) == list(pages)[1:]
    assert "Skipping the page number, 0, as it is not a valid page number." in caplog.text

def test_mixed_types(caplog):
    pages = ['00', 1, 2, 3, '10']
    page_list_input = PageListInput(pages) # type:ignore
    assert list(page_list_input.page_numbers) == sorted(int(page) for page in pages)[1:] # type:ignore
    assert "Skipping the page number, 0, as it is not a valid page number." in caplog.text


def test_invalid_inputs(caplog):
    with pytest.raises(ValidationError):
        # floats in are invalid and PageListInput errors as a result
        _ = PageListInput([1.2, 3.4, 5.6]) # type:ignore
    #assert "Expected a provided page value to be a number. Received: '1.2'" in caplog.text

    v = map
    with pytest.raises(ValidationError):
        # the PageListInput model shouldn't accept functions as input
        _ = PageListInput(v) # type:ignore
    assert f"Expected a list, set, or generator containing page numbers. Received: '{type(v)}'" in caplog.text

    with pytest.raises(ValidationError):
        # should initialize due to a wrong type
        _ = PageListInput('this is also invalid') # type:ignore
