# /exceptions/data_exceptions.py
"""Implements exceptions for handling scenarios that could occur during the parsing, extraction, and processing of
response data."""


class ResponseProcessingException(Exception):
    """Base Exception for handling errors in response parsing and processing."""


class DataParsingException(ResponseProcessingException):
    """Base exception for errors that occur during data parsing."""


class InvalidDataFormatException(DataParsingException):
    """Exception raised for errors in the input data format."""


class DataExtractionException(ResponseProcessingException):
    """Base exception for errors that occur during data extraction."""


class FieldNotFoundException(DataExtractionException):
    """Exception raised when an expected field is not found in the data."""


class DataProcessingException(ResponseProcessingException):
    """Base exception for errors that occur during data processing."""


class DataValidationException(DataProcessingException):
    """Exception raised for data validation errors."""


__all__ = [
    "ResponseProcessingException",
    "DataParsingException",
    "InvalidDataFormatException",
    "DataExtractionException",
    "FieldNotFoundException",
    "DataProcessingException",
    "DataValidationException",
]
