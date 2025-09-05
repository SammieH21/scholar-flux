import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import requests
import requests_mock
from urllib.parse import urlparse
import logging
import re

from scholar_flux.api import SearchAPI, SearchCoordinator
from scholar_flux.api.models import ProcessedResponse, ErrorResponse, APIResponse


@patch("scholar_flux.api.search_coordinator.SearchCoordinator.search")
def test_multisearch(mock_search, mock_successful_response, mock_rate_limit_exceeded_response, caplog):
    """
    Test for whether the defaults are specified correctly and whether the mocked response is processed
    as intended throughout the coordinator
    """
    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]
    success_response = ProcessedResponse(response = mock_successful_response,
                                         extracted_records = extracted_records
                                           )
    rate_limit_response = ErrorResponse(response=mock_rate_limit_exceeded_response,
                                        message='Rate limit exceeded')

    page_results = [
        success_response,
        success_response,
        rate_limit_response
    ]

    page_list = [1, 2, 3]

    mock_search.side_effect = page_results

    api = SearchAPI.from_defaults(
        provider_name='plos',
        query="test",
        base_url="https://api.example.com",
        records_per_page=len(extracted_records),
        request_delay=0
    )
    coordinator = SearchCoordinator(api)

    pages = coordinator.search_pages(page_list)
    assert len(pages) == 3
    for page, expected_response in zip(pages, page_results):
        assert page is not None and page.status_code == expected_response.status_code
