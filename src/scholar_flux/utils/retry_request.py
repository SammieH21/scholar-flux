import requests
import time
import os   


import logging
logger = logging.getLogger(__name__)

def retry_request(url, params=None, retries=2, retry_delay=2.0, request_timeout=10):
    """Send a request to the API, with retry logic."""
    attempt = 0
    while attempt < retries:
        response = requests.get(url,params, timeout=request_timeout)
        if response.ok:
            return response  # Successful response
        attempt += 1
        logger.info(f"Retrying request, attempt {attempt}...")
        time.sleep(retry_delay)
        retry_delay *= 2  # Exponential back-off
    logger.error(f"Request failed after {retries} attempts.")
    return response

response = retry_request('https://www.google.com/')