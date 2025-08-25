from typing import Union
from scholar_flux.api.models.response import ProcessedResponse, ErrorResponse

ResponseResult = Union[ProcessedResponse, ErrorResponse]
