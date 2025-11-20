# /data/abc_processor.py
"""The scholar_flux.data.abc_processor module defines the ABCDataProcessor, which in turn, defines the core, abstract
logic that all scholar_flux data processor subclasses will implement.

This module defines the abstract methods and types that each processor will use for compatibility with the
SearchCoordinator in the processing step.

"""
from typing import Optional, Tuple, Any
from typing_extensions import Self
from abc import ABC, abstractmethod
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.exceptions import DataValidationException
import copy
import threading


class ABCDataProcessor(ABC):
    """The ABCDataProcessor is the base class from which all other processors are created.

    The purpose of all subclasses of the ABCDataProcessor is to transform extracted records into a format suitable
    for future data processing pipelines. More specifically, its responsibilities include:

        Processing a specific key from record by joining non-None values into a string.

        Processing a record dictionary to extract record and article content, creating a processed record dictionary
        with an abstract field.

        Processing a list of raw page record dict data from the API response based on record keys.

    All subclasses, at minimum, are expected to implement the process_page method which would effectively transform
    the records of each page into the intended list of dictionaries.

    """

    def __init__(self, *args, **kwargs) -> None:
        """Initializes record keys and header/body paths in the object instance using defined methods."""
        pass

    def load_data(self, *args, **kwargs):
        """Helper method that is optionally implemented by subclasses to load JSON data into customized implementations
        of processors."""
        raise NotImplementedError

    def define_record_keys(self, *args, **kwargs) -> Optional[dict]:
        """Abstract method to be optionally implemented to determine record keys that should be parsed to process each
        record."""
        pass

    def ignore_record_keys(self, *args, **kwargs) -> Optional[list]:
        """Abstract method to be optionally implemented to ignore certain keys in records when processing records."""
        pass

    def define_record_path(self, *args, **kwargs) -> Optional[Tuple]:
        """Abstract method to be optionally implemented to Define header and body paths for record extraction, with
        default paths provided if not specified."""
        pass

    def record_filter(self, *args, **kwargs) -> Optional[bool]:
        """Optional filter implementation to handle record screening using regex or other logic.

        Subclasses can customize filtering if required.

        """
        pass

    def discover_keys(self, *args, **kwargs) -> Optional[dict]:
        """Abstract method to be optionally implemented to discover nested key paths in json data structures."""
        pass

    def process_key(self, *args, **kwargs) -> Optional[str]:
        """Abstract method to be optionally implemented for processing keys from records."""
        pass

    def process_text(self, *args, **kwargs) -> Optional[str]:
        """Abstract method to be optionally implemented for processing a record dictionary to extract record and article
        content, creating a processed record dictionary with an abstract field."""
        pass

    def process_record(self, *args, **kwargs) -> Optional[dict]:
        """Abstract method to be optionally implemented for processing a single record in a json data structure.

        Used to extract record data and article content, creating a processed record dictionary with an abstract field.

        """
        pass

    @abstractmethod
    def process_page(self, *args, **kwargs) -> list[dict]:
        """Must be implemented in subclasses for processing entire pages of records."""
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> list[dict]:
        """Convenience method for using child classes to call .process_page.

        Example:
            processor = ABCDataProcessor()
            processor(extracted_records)

        """
        return self.process_page(*args, **kwargs)

    @classmethod
    def _validate_inputs(
        cls,
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        regex: Optional[bool] = None,
        *,
        record_keys: Optional[
            dict[str | int, Any] | dict[str, Any] | list[list[str | int]] | list[list[str]] | list[str]
        ] = None,
        value_delimiter: Optional[str] = None,
    ):
        """Helper class for ensuring that inputs to data processor subclasses match the intended types."""
        if record_keys is not None and not isinstance(record_keys, list) and not isinstance(record_keys, dict):
            raise DataValidationException(f"record_keys must be a list or dict, got {type(record_keys)}")
        if ignore_keys is not None and not isinstance(ignore_keys, list):
            raise DataValidationException(f"ignore_keys must be a list, got {type(ignore_keys)}")
        if keep_keys is not None and not isinstance(keep_keys, list):
            raise DataValidationException(f"keep_keys must be a list, got {type(keep_keys)}")
        if regex is not None and not isinstance(regex, bool):
            raise DataValidationException(f"regex must be a True/False value, got {type(regex)}")
        if value_delimiter is not None and not isinstance(value_delimiter, str):
            raise DataValidationException(f"value_delimiter must be a string, got {type(value_delimiter)}")

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for quickly showing a representation of the overall structure of the current Processor
        subclass. The instance uses the generate_repr helper function to produce human-readable representations of the
        core structure of the processing configuration along with its defaults.

        Returns:
            str: The structure of the current Processor subclass as a string.

        """
        return generate_repr(self, exclude={"json_data"}, flatten=flatten, show_value_attributes=show_value_attributes)

    def __copy__(self) -> Self:
        """Helper method for copying the current implementation of a class minus a lock if used."""
        cls = self.__class__
        result = cls.__new__(cls)
        for k, v in self.__dict__.items():
            if isinstance(v, type(threading.Lock())):
                setattr(result, k, threading.Lock())
            else:
                setattr(result, k, v)
        return result

    def __deepcopy__(self, memo) -> Self:
        """Helper method for deep copying the current implementation of a class minus the lock."""
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if isinstance(v, type(threading.Lock())):
                setattr(result, k, threading.Lock())
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    def __repr__(self) -> str:
        """Method for identifying the current implementation and subclasses of the ABCDataProcessor.

        Useful for showing the options being used to process the records that originate from the parsed api response.

        """
        return self.structure()


__all__ = ["ABCDataProcessor"]
