# /api/models/search_inputs.py
"""The scholar_flux.api.models.search_inputs module implements the PageListInput RootModel for multi-page searches.

The PageListInput model is designed to validate and prepare lists and iterables of page numbers for multi-page retrieval
using the `SearchCoordinator.search_pages` method.

"""

from typing import Sequence, Mapping, Iterable
from pydantic import RootModel, field_validator
import logging

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

    def __repr__(self) -> str:
        """Provides a simple string representation of the current page list input."""
        class_name = self.__class__.__name__
        vals = ", ".join(str(v) for v in self.page_numbers)
        return f"{class_name}({vals})"

    @property
    def page_numbers(self) -> Sequence[int]:
        """Returns the sequence of validated page numbers as a list."""
        return list(self.root)


__all__ = ["PageListInput"]
