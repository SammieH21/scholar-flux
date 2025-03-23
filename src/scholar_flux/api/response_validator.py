import requests
import logging
from typing import Dict, List, Optional, Union, Tuple
from ..exceptions.api_exceptions import RateLimitExceededException, RequestFailedException

logger = logging.getLogger(__name__)


# In validate_response:



class ResponseValidator:
    
    @staticmethod
    def validate_response(response: requests.Response) -> bool:
        """
        Validates the given response for any HTTP errors and raises an exception if necessary.
        Returns True if the response is valid, otherwise raises RequestFailedException.
        """
        try:
            response.raise_for_status()
            logger.debug(f"Successfully received response from {response.url}")
            return True
        except requests.HTTPError as e:
            logger.error('Response validation failed: {}'.format(str(e)))
            raise RequestFailedException(response, str(e))

            
        #if response.status_code == 429:
        #        raise RetryLimitExceededException(f"Too many requests...\{error_details}")

    # @staticmethod
    # def validate_content(response: requests.Response, expected_format: str = "json") -> bool:
    #     """
    #     Validates the response content type.
    #     """
    #     content_type = response.headers.get('Content-Type', '')
    #     if expected_format == "json" and 'application/json' in content_type:
    #         return True
    #     elif expected_format == "xml" and 'application/xml' in content_type:
    #         return True
    #     else:
    #         logger.error("Unexpected response format.")
