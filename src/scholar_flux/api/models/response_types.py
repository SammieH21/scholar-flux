# /api/models/response_types.py
"""Helper module used to define response types returned by scholar-flux after API response retrieval and processing.

The APIResponseType is a union of different possible response types that can be received from a SearchCoordinator:
    - ProcessedResponse: A successfully processed response containing parsed response metadata, and processed records.
    - ErrorResponse: Indicates that an error has occurred during response retrieval and/or processing when unsuccessful.
    - NonResponse: `ErrorResponse` subclass indicating when an error prevents the successful retrieval of a response.

"""

from typing import Union
from scholar_flux.api.models.responses import ProcessedResponse, ErrorResponse

APIResponseType = Union[ProcessedResponse, ErrorResponse]

__all__ = ["APIResponseType"]
