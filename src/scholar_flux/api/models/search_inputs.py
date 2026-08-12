# /api/models/search_inputs.py
"""The scholar_flux.api.models.search_inputs module implements the PageListInput RootModel for multi-page searches.

The PageListInput model is designed to validate and prepare lists and iterables of page numbers for multi-page retrieval
using the `SearchCoordinator.search_pages` method.

"""

from collections.abc import Sequence, Mapping, Iterable
from typing_extensions import Self
from pydantic import RootModel, field_validator
from math import ceil
import logging

from scholar_flux.exceptions.api_exceptions import APIParameterException

logger = logging.getLogger(__name__)


class PageListInput(RootModel[Sequence[int]]):
    """Helper class for processing page information in a predictable manner.

    The PageListInput class expects to receive a list, string, or generator that contains at least one page number.
    If a singular integer is received, the result is transformed into a single-item list containing that integer.

    Args:
        root (Sequence[int]): A list containing at least one page number.

    Examples:
        >>> from scholar_flux.api.models import PageListInput
        >>> PageListInput(5)
        PageListInput([5])
        >>> PageListInput(range(5))
        PageListInput([0, 1, 2, 3, 4])

    """

    @field_validator("root", mode="before")
    def page_validation(cls, v: str | int | Sequence[int | str]) -> Sequence[int]:
        """Processes the page input to ensure that a list of integers is returned if the received page list is in a
        valid format.

        Args:
            v (str | int | Sequence[int | str]): A page or sequence of pages to be formatted as a list of pages.
        Returns:
            Sequence[int]: A validated, formatted sequence of page numbers assuming successful page validation

        Raises:
            ValidationError: Internally raised via pydantic if a ValueError is encountered
                             (if the input is not exclusively a page or list of page numbers)

        """
        if isinstance(v, (str, int)):
            return [cls.process_page(v)]

        if isinstance(v, (Sequence, Iterable)) and not isinstance(v, Mapping):
            return sorted(set({cls.process_page(v_i) for v_i in v}))

        err_msg = f"Expected a list, set, or generator containing page numbers. Received: '{type(v)}'"
        logger.error(err_msg)
        raise ValueError(err_msg)

    @classmethod
    def process_page(cls, page_value: str | int) -> int:
        """Helper method for ensuring that each value in the sequence is a numeric string or whole number.

        Note that this function will not throw an error for negative pages as that is handled at a later step
        in the page search process.

        Args:
            page_value (str | int): The value to be converted if it is not already an integer

        Returns:
            int: A validated integer if the page can be converted to an integer and is not a float

        Raises:
            ValueError: When the value is not an integer or numeric string to be converted to an integer

        """
        if isinstance(page_value, str) and page_value.isnumeric():
            page_value = int(page_value)

        if not isinstance(page_value, int):
            err_msg = f"Expected a provided page value to be a number. Received: '{page_value}'"
            logger.error(err_msg)
            raise ValueError(err_msg)

        return page_value

    @classmethod
    def from_record_count(cls, min_records: int, records_per_page: int, page_offset: int = 0) -> Self:
        """Helper method for calculating the total number of pages required to retrieve at least `min_records` records.

        Args:
            min_records (int):
                The total number of records to retrieve sequentially.
            records_per_page (int):
                The total number of records that are retrieved per page.
            page_offset (int):
                The total number of pages to skip before beginning record retrieval (0 by default). When the provided
                value is not a non-negative integer, this parameter is coerced to 0 and a warning is triggered.

        Returns:
            PageListInput:
                The calculated page range used to retrieve at least `min_records` records given `records_per_page`.

        Examples:
            >>> from scholar_flux.api.models import PageListInput
            >>> PageListInput.from_record_count(20, 10, 0)
            PageListInput(1, 2)

            >>> PageListInput.from_record_count(20, 10, 2)
            PageListInput(3, 4)

            >>> PageListInput.from_record_count(15, 10, 1)
            PageListInput(2, 3)

            # triggers a warning for page_offset (non-integers are coerced to 0):
            >>> PageListInput.from_record_count(20, 10, None)
            PageListInput(1, 2)

            >>> PageListInput.from_record_count(0, 10, 0)
            PageListInput()

        Note:
            This method expects a positive integer for `min_records` from which to calculate the page range required to
            retrieve at least `min_records`. Specifying 0 for `min_records` will result in an empty list of pages that
            essentially functions as a no-op search returning an empty list from `SearchCoordinator.search_records`.

        """
        if not isinstance(min_records, int) or min_records < 0:
            raise APIParameterException(
                f"Expected `min_records` to be a positive integer, but received value '{min_records}'"
            )

        if not isinstance(page_offset, int) or page_offset < 0:
            logger.warning(
                f"Expected a valid, non-negative integer for `page_offset`, but received '{page_offset}'. Defaulting "
                "to 0 instead..."
            )
            page_offset = 0
        page_start = 1 + page_offset
        total_pages = max(0, ceil(min_records / records_per_page)) if records_per_page else 0
        page_stop = page_start + total_pages
        pages = range(page_start, page_stop)
        return cls(pages)

    @property
    def page_numbers(self) -> Sequence[int]:
        """Returns the sequence of validated page numbers as a list."""
        return list(self.root)

    def __repr__(self) -> str:
        """Provides a simple string representation of the current page list input."""
        class_name = self.__class__.__name__
        vals = ", ".join(str(v) for v in self.page_numbers)
        return f"{class_name}({vals})"

    def __bool__(self) -> bool:
        """Helper method that returns False if `PageListInput.page_numbers` is empty and True otherwise."""
        return bool(self.root)


__all__ = ["PageListInput"]
