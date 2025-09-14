from typing import Optional, Tuple
from abc import ABC, abstractmethod
from scholar_flux.utils.repr_utils import generate_repr


class ABCDataProcessor(ABC):
    """
    The ABCDataProcessor is the base class from which all other processors are created.

    The purpose of all subclasses of the ABCDataProcessor is to transform extracted records into a format suitable
    for future data processing pipelines. More specifically, its responsibilities include:

        Processing a specific key from record by joining non-None values into a string.

        Processing a record dictionary to extract record and article content, creating a processed record dictionar
        with an abstract field.

        Processing a list of raw page record dict data from the API response based on record keys.

    All subclasses, at minimum, are expected to implement the process_page method which would effectively transform
    the records of each page into the intended list of dictionaries.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        Initializes record keys and header/body paths in the object instance using defined methods.

        Returns:
        - None
        """
        pass

    def load_data(self, *args, **kwargs):
        raise NotImplementedError

    def define_record_keys(self, *args, **kwargs) -> Optional[dict]:
        """
        Abstract method to be optionally implemented to determine record keys
        that should be parsed to process each record
        """
        pass

    def ignore_record_keys(self, *args, **kwargs) -> Optional[list]:
        """
        Abstract method to be optionally implemented to ignore certain keys in records when processing records
        """
        pass

    def define_record_path(self, *args, **kwargs) -> Optional[Tuple]:
        """
        Abstract method to be optionally implemented to Define header and body paths for record extraction,
        with default paths provided if not specified
        """
        pass

    def record_filter(self, *args, **kwargs) -> Optional[bool]:
        """
        Optional filter implementation to handle record screening using regex or other logic.
        Subclasses can customize filtering if required.
        """
        pass

    def discover_keys(self, *args, **kwargs) -> Optional[dict]:
        """
        Abstract method to be optionally implemented to discover nested key paths in json data structures
        """
        pass

    def process_key(self, *args, **kwargs) -> Optional[str]:
        """
        Abstract method to be optionally implemented for processing keys from records
        """
        pass

    def process_text(self, *args, **kwargs) -> Optional[str]:
        """
        Abstract method to be optionally implemented for processing a record dictionary to extract record
        and article content, creating a processed record dictionary with an abstract field.
        """
        pass

    def process_record(self, *args, **kwargs) -> Optional[dict]:
        """
        Abstract method to optionally implemented for processing a single record in a json data structure.
        Used extract record data and article content, creating a processed record dictionary with an abstract field.
        """
        pass

    @abstractmethod
    def process_page(self, *args, **kwargs) -> list[dict]:
        """Must be implemented in subclasses for processing entire pages of records."""
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> list[dict]:
        """
        Convenience method for using child classes to call .process_page

        Example:
            processor = ABCDataProcessor()
            processor(extracted_records)
        """
        return self.process_page(*args, **kwargs)

    def __repr__(self) -> str:
        """
        Method for identifying the current implementation and subclasses of the ABCDataProcessor.
        Useful for showing the options being used to process the records that originate
        from the parsed api response.
        """
        return generate_repr(self, exclude=("json_data",))
