from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from ..data.data_extractor import DataExtractor
import logging
logger = logging.getLogger(__name__)

class DataExtractorFactory:
    def __init__(self):
        # This dictionary maps extractor names to their specific factory methods
        self.extractors = {
            "PAM": self.create_pam_extractor,
            "JSON":self.create_json_extractor
            # Add more mappings as necessary
        }

    def get_extractor(self, name: str) -> Optional[DataExtractor]:
        """ Retrieves a DataExtractor based on a given name. """
        factory_method = self.extractors.get(name)
        if not factory_method:
            logger.error(f"No extractor found for {name}")
            return None
        return factory_method()

    @staticmethod
    def create_pam_extractor() -> DataExtractor:
        """ Factory method for creating a DataExtractor configured for PAM responses. """
        metadata_path = {
            'total_records': ['response', 'result', 'total'],
            'page_length': ['response', 'result', 'recordsDisplayed'],
            'total_displayed_records': ['response', 'result', 'pageLength'],
        }
        record_path = ['response', 'records', 'record']
        return DataExtractor(record_path=record_path, metadata_path_overrides=metadata_path)
    @staticmethod
    def create_json_extractor() -> DataExtractor:
        """ Factory method for creating a DataExtractor configured for PAM responses. """
        metadata_path = {
            'total_records': ['result', 'total'],
            'page_length': ['result','recordsDisplayed'],
            'total_displayed_records': ['result','pageLength'],
        }
        record_path = ['records']
        return DataExtractor(record_path=record_path, metadata_path_overrides=metadata_path)

# Usage
factory = DataExtractorFactory()