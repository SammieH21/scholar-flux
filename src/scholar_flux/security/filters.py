# /security/filters.py
"""The scholar_flux.security.filters module implements the basic foundational filter used by logging utilities to
determine how text will be masked and redacted prior to being stored in file handlers or written to the console.

This module uses the `SensitiveDataMasker` class to flag and redact text prior to it ever reaching the console or file
via the `logging` module.

"""
import logging
from typing import Optional
from scholar_flux.security.masker import SensitiveDataMasker


class MaskingFilter(logging.Filter):
    """Custom class for adding a masking to the logs: Uses the SensitiveDataMasker in order to enforce the rules
    detailing which fields should be logged. By default, the SensitiveDataMasker masks API keys and email parameters in
    requests to APIs sent via scholar_flux.

    Initialized MaskingFilters can also be updated without re-instantiation by adding or removing patterns
    from the set of all patterns within the received Masker.

    This class can otherwise be added to other loggers with minimal effort:
        >>> import logging
        >>> from scholar_flux.security import MaskingFilter # contains the filter
        >>> formatting = "%(name)s - %(levelname)s - %(message)s" # custom format
        >>> logger = logging.getLogger('security_logger') # gets or creates a new logger
        >>> logging.basicConfig(level=logging.DEBUG, format=formatting) # set the level and formatting for the log
        >>> logging_filter = MaskingFilter() # creating a new filter
        >>> logger.addFilter(logging_filter) # adding the filter and formatting rules
        >>> logger.info("The following api key should be filtered: API_KEY='an_api_key_that_needs_to_be_filtered'")
        # OUTPUT: security_logger - INFO - The following api key should be filtered: API_KEY='***'

    """

    def __init__(self, masker: Optional[SensitiveDataMasker] = None):
        """By default, this implementation is applied in the initialization of the package in scholar_flux.__init__ on
        import, so this class does not need to be applied directly.

        Args:
            masker (Optional[SensitiveDataMasker]): The actual implementation responsible for masking text matching
               patterns. Note that if a masker is not passed, the MaskingFilter will initialize a masker directly.

        """
        super().__init__()
        self.masker = masker or SensitiveDataMasker()

    def filter(self, record) -> bool:
        """Helper method used by the logging.Logger class when adding custom filters to the logging module.

        This class will always return True after an attempt to mask sensitive fields is completed.

        """
        if record.args:
            record.args = tuple(self.masker.mask_text(arg) if isinstance(arg, str) else arg for arg in record.args)
        if isinstance(record.msg, str):
            record.msg = self.masker.mask_text(record.msg)
        return True


__all__ = ["MaskingFilter"]
