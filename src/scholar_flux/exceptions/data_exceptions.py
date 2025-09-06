# data_exceptions.py
class ResponseProcessingException(Exception):
    """Base Exception for handling errors in response parsing and processing"""


class DataParsingException(ResponseProcessingException):
    """Base exception for errors that occur during data parsing."""

    pass


class InvalidDataFormatException(DataParsingException):
    """Exception raised for errors in the input data format."""

    pass


class RequiredFieldMissingException(DataParsingException):
    """Exception raised when a required field is missing in the input data."""

    def __init__(self, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_name = field_name
        self.message = f"Required field '{self.field_name}' is missing."


class DataExtractionException(ResponseProcessingException):
    """Base exception for errors that occur during data extraction."""

    pass


class FieldNotFoundException(DataExtractionException):
    """Exception raised when an expected field is not found in the data."""

    def __init__(self, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_name = field_name
        self.message = f"Field '{self.field_name}' not found in the data."


class DataProcessingException(ResponseProcessingException):
    """Base exception for errors that occur during data processing."""

    pass


class DataValidationException(DataProcessingException):
    """Exception raised for data validation errors."""

    def __init__(self, validation_errors, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validation_errors = validation_errors
        self.message = "Data validation failed with errors: " + ", ".join(validation_errors)
