# /api/models/response_types.py
"""
Helper module used to indicate response types that can be retrieved from an API provider after processing

APIResponseType: Indicates the type of response received from a SearchCoordinator:
    - ProcessedResponse: A successfully retrieved and prepared response that containing parsed and processed records
    - ErrorResponse: Indicates the occurrence and type of an error when retrieving and/or processing the response
    - NoResponse: Indicates that an error that prevented the retrieval of a response.
"""
from typing import Union
from scholar_flux.api.models.responses import ProcessedResponse, ErrorResponse

APIResponseType = Union[ProcessedResponse, ErrorResponse]

__all__ = ["APIResponseType"]
