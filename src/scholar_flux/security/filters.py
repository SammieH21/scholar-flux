import logging
from typing import Optional
from scholar_flux.security.masker import SensitiveDataMasker

class MaskingFilter(logging.Filter):
    def __init__(self, masker: Optional[SensitiveDataMasker] = None):
        """
        Custom class for adding a masking to the logs: Uses the
        SensitiveDataMasker in order to enforce logging
        """
        super().__init__()
        self.masker = masker or SensitiveDataMasker()

    def filter(self, record) -> bool:
        if record.args:
            record.args = tuple(
                self.masker.mask_text(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        if isinstance(record.msg, str):
            record.msg = self.masker.mask_text(record.msg)
        return True

